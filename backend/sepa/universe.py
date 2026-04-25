"""Scanning universe — tickers we run SEPA against.

Defaults to a curated list of ~250 liquid US names across growth-friendly
sectors (what Minervini typically hunts in). Override via SEPA_UNIVERSE env var
or by editing UNIVERSE below.
"""
from __future__ import annotations

import os
from pathlib import Path

# Liquid growth + momentum names. Edit freely.
UNIVERSE: list[str] = [
    # Mega-cap tech
    "NVDA", "MSFT", "AAPL", "META", "GOOGL", "AMZN", "TSLA", "AVGO", "ORCL", "NFLX",
    # Semis / AI infra
    "AMD", "ASML", "TSM", "MU", "ARM", "MRVL", "LRCX", "AMAT", "KLAC", "SMCI",
    "CRDO", "ALAB", "ANET", "CRWV", "NEBIUS",
    # Software / cloud
    "CRM", "NOW", "SNOW", "DDOG", "NET", "CRWD", "PANW", "ZS", "MDB", "PLTR",
    "SHOP", "TEAM", "WDAY", "HUBS", "CFLX", "SMAR", "TOST",
    # Consumer growth
    "ABNB", "UBER", "DASH", "BKNG", "CMG", "LULU", "DECK", "COST", "WMT",
    # Health / biotech leaders
    "LLY", "UNH", "ISRG", "VRTX", "REGN", "BMRN", "RMD", "BSX",
    # Fintech / payments
    "V", "MA", "PYPL", "AXP", "COIN", "HOOD", "SQ", "SOFI", "NU", "MELI",
    # Energy / industrials / materials
    "CEG", "VST", "GEV", "ETN", "PH", "CAT", "DE", "FSLR", "ENPH",
    # China ADR growth
    "BABA", "PDD", "JD", "NIO", "LI", "XPEV",
    # Small/mid momentum movers (edit freely)
    "RKLB", "ACHR", "JOBY", "SERV", "OKLO", "LUNR", "ASTS", "AEHR", "IONQ",
    "RGTI", "QBTS", "BBAI", "SOUN", "TEM", "HIMS", "DUOL", "RBLX", "DKNG",
    "SPOT", "RDDT", "APP", "APPN", "PATH", "BILL", "DOCN",
    # Anchor / benchmarks (not traded but used for RS math)
    "SPY", "QQQ", "IWM",
]


def load_universe() -> list[str]:
    """Resolve the active universe.

    Priority:
    1. SEPA_UNIVERSE_FILE env var pointing to a text file (one ticker per line)
    2. SEPA_UNIVERSE env var comma-separated
    3. Default UNIVERSE above
    """
    file_path = os.getenv("SEPA_UNIVERSE_FILE")
    if file_path and Path(file_path).exists():
        return [ln.strip().upper() for ln in Path(file_path).read_text().splitlines() if ln.strip()]
    env = os.getenv("SEPA_UNIVERSE")
    if env:
        return [s.strip().upper() for s in env.split(",") if s.strip()]
    return list(dict.fromkeys(UNIVERSE))  # dedup preserving order


BENCHMARK = "SPY"
