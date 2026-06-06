"""Political / government disclosure map — BACKEND mirror of
frontend/src/lib/politicalDisclosures.ts.

The FE file is the source of truth the user curates (OGE filings + reputable
news). Keep this in sync when entries change there. Ticker -> categories.

Categories: potus_family | govt_investment | govt_contractor | inferred.

INFORMATIONAL only — a disclosed position is NOT a buy/sell signal and does not
imply the official's family has private information (Ajay 2026-05-28).
"""
from __future__ import annotations

POLITICAL: dict[str, list[str]] = {
    # POTUS-family disclosed positions
    "NVDA": ["potus_family"], "MSFT": ["potus_family"], "AVGO": ["potus_family"],
    "AMZN": ["potus_family"], "AAPL": ["potus_family"], "ORCL": ["potus_family"],
    "DELL": ["potus_family"], "ADBE": ["potus_family"], "TXN": ["potus_family"],
    "MSI": ["potus_family"], "NOW": ["potus_family"], "META": ["potus_family"],
    "AMD": ["potus_family"], "GS": ["potus_family"], "GOOGL": ["potus_family"],
    "ABNB": ["potus_family"], "DASH": ["potus_family"], "MU": ["potus_family"],
    "BE": ["potus_family"], "BAC": ["potus_family"], "PG": ["potus_family"],
    "BA": ["potus_family"], "LLY": ["potus_family"], "COIN": ["potus_family"],
    "SOFI": ["potus_family"], "WMT": ["potus_family"], "INTU": ["potus_family"],
    "WDAY": ["potus_family"],
    # POTUS-family + direct U.S. government involvement
    "INTC": ["potus_family", "govt_investment"],   # CHIPS Act equity stake
    "PLTR": ["potus_family", "govt_contractor"],
    "HOOD": ["potus_family", "govt_contractor"],   # 'Trump Accounts' trustee
    # inferred (scan-classified, softer)
    "QBTS": ["inferred"], "RGTI": ["inferred"], "INFQ": ["inferred"],
    "NN": ["inferred"], "PLUG": ["inferred"],
}


def categories_for(ticker: str) -> list:
    return POLITICAL.get((ticker or "").upper(), [])
