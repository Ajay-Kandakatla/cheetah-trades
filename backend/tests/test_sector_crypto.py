"""Crypto EQUITIES — the category, not the coins (2026-09-12).

Ajay, in one message: *"Ignore Crypo.."* and then *"BTW talking about Crypto
there are so many Crypto related stocks are missin gin ours like IREN, Mining
stocks like bit coind related can you create a new caterogy for crypto please
in to our apps"*.

THOSE TWO ARE NOT IN TENSION and the distinction is the whole point:

  TOKENS   BNB / ETH / XRP — refused outright. They are not scannable US
           equities, and they turned up as three of the eight uncovered names
           the tracked traders mention (traders/curate.NEVER_ADD).
  EQUITIES the listed companies whose earnings move with the coin — miners,
           exchanges, treasury holders. Exactly what this app screens.

EVERY TICKER IN THE ROSTER WAS PRICE-VALIDATED against production data before
it was added. Two candidates failed and are named in the source so nobody
re-adds them from memory.
"""
from __future__ import annotations

import pytest

from supply_demand import sectors as S
from traders import curate as C


def _sector():
    return next(s for s in S.SECTORS if s["id"] == "crypto_equities")


def test_the_sector_exists_and_leads_with_the_name_he_asked_for():
    sec = _sector()
    assert sec["label"] == "Crypto Miners / Equities"
    assert "IREN" in sec["sp_tickers"]


def test_it_covers_miners_exchanges_AND_treasury_holders():
    t = set(_sector()["sp_tickers"])
    assert {"MARA", "RIOT", "CLSK", "BITF", "HIVE"} <= t, "miners"
    assert {"COIN", "HOOD", "GLXY"} <= t, "exchanges / brokers"
    assert {"MSTR", "SMLR"} <= t, "treasury holders"


def test_THE_CENTRAL_DISTINCTION_the_COINS_are_still_refused():
    """"Ignore Crypo" and "create a new caterogy for crypto" both hold."""
    for token in ("BNB", "ETH", "XRP", "BTC", "SOL", "DOGE"):
        assert token in C.NEVER_ADD
        ok, why = C.validate(token)
        assert ok is False and "crypto" in why
    assert not (set(_sector()["sp_tickers"]) & C.NEVER_ADD), \
        "no token may appear in an EQUITY roster"


def test_every_roster_name_is_actually_SCANNABLE():
    """A category whose names are not in `full` is a category that displays
    stocks no board, scan or alert can ever see."""
    from sepa.universe import load_universe
    uni = {s.upper() for s in load_universe("full")}
    missing = [t for t in _sector()["sp_tickers"] if t not in uni]
    assert missing == [], f"not in the scan universe: {missing}"


def test_NEGATIVE_the_names_that_FAILED_price_validation_are_absent():
    """GREE returned 7 bars. SDIG returned 126 bars but had stopped printing —
    Stronghold was acquired by Bitfarms — which is exactly the case the
    liveness gate was added for. Neither may be in the roster or the universe."""
    from sepa.universe import load_universe
    uni = {s.upper() for s in load_universe("full")}
    for dead in ("GREE", "SDIG"):
        assert dead not in _sector()["sp_tickers"]
        assert dead not in uni


def test_NEGATIVE_no_member_collides_with_another_sector_the_TER_TRAP():
    """macro_risk builds ONE bucket per ticker with setdefault — first sector
    wins — so a name in two sectors gets silently re-bucketed."""
    from collections import Counter
    seen = Counter()
    for s in S.SECTORS:
        for t in s.get("sp_tickers") or []:
            seen[t] += 1
    dupes = [t for t in _sector()["sp_tickers"] if seen[t] > 1]
    assert dupes == [], f"also in another sector: {dupes}"


def test_NEGATIVE_it_invents_no_supply_gap():
    """Hashrate expands to meet price and difficulty adjusts it away — there is
    no bottleneck to own, so the field stays off and the thesis says so."""
    sec = _sector()
    assert not sec.get("gap_economics")
    assert "not a supply gap" in sec["thesis"].lower()


def test_the_thesis_states_the_AI_HPC_pivot_and_the_treasury_caveat():
    """Several miners are no longer a pure crypto bet, and a treasury holder is
    a levered proxy for the coin rather than an operating business. Both change
    how a row should be read."""
    th = _sector()["thesis"].lower()
    assert "hpc" in th or "ai/hpc" in th
    assert "levered proxy" in th


def test_the_crypto_ETFs_are_carried_but_CANNOT_ALERT():
    """Same deal he accepted for the robotics funds: a provider reports AUM for
    a fund and never a market cap, and zone_store keeps only a KNOWN cap over
    MIN_CAP_USD — so no ETF ever gets zone bands or fires a demand push."""
    from sepa.universe import load_universe
    uni = {s.upper() for s in load_universe("full")}
    for etf in ("IBIT", "WGMI", "BITQ", "BLOK"):
        assert etf in uni, f"{etf} must at least chart and scan"
    # and they are NOT in the equity roster, which is about operating companies
    assert not ({"IBIT", "WGMI", "BITQ", "BLOK"} & set(_sector()["sp_tickers"]))
