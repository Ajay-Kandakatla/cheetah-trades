"""Curated giant-fund registry — the funds whose full 13F portfolios we track.

Mirrors the user-curated tier list in frontend/src/lib/fundTiers.ts
(Tier S = legendary stock-pickers, Tier A = active alpha-seekers). Every CIK
below was resolved against SEC EDGAR on 2026-06-10 and verified to be an
ACTIVE 13F-HR filer (most recent filing 2026-05-xx for the Q1 2026 period).

EDIT THIS FILE to add/remove funds — everything downstream (filing fetch,
flow aggregation, rotation views) keys off this list.

Index giants (Vanguard / BlackRock / State Street / Geode...) are deliberately
NOT here: their flow is mandate-driven, not conviction, and corporate-entity
restructurings show up as fake "+100% new position" moves that would swamp
every chart. Same honesty caveat as fundTiers.ts.

`style` tags how to read the fund's flow:
  picker   — concentrated conviction books; their adds MEAN something
  quant    — multi-strat / systematic; huge churn, weak per-name signal
  activist — concentrated but slow-moving stakes
The aggregate view lets the UI down-weight or hide quants.
"""
from __future__ import annotations

from typing import List, Optional

Fund = dict  # {cik:int, name:str, short:str, tier:'S'|'A', manager:str, style:str}

FUNDS: List[Fund] = [
    # --- Tier S — legendary stock-pickers -------------------------------
    {"cik": 1067983, "name": "Berkshire Hathaway Inc",            "short": "Berkshire",      "tier": "S", "manager": "Warren Buffett",      "style": "picker"},
    {"cik": 1336528, "name": "Pershing Square Capital Management","short": "Pershing Sq",    "tier": "S", "manager": "Bill Ackman",         "style": "activist"},
    {"cik": 1079114, "name": "Greenlight Capital Inc",            "short": "Greenlight",     "tier": "S", "manager": "David Einhorn",       "style": "picker"},
    {"cik": 1649339, "name": "Scion Asset Management LLC",        "short": "Scion",          "tier": "S", "manager": "Michael Burry",       "style": "picker"},
    {"cik": 1029160, "name": "Soros Fund Management LLC",         "short": "Soros",          "tier": "S", "manager": "George Soros",        "style": "picker"},
    {"cik": 1037389, "name": "Renaissance Technologies LLC",      "short": "RenTech",        "tier": "S", "manager": "Medallion (Simons)",  "style": "quant"},
    {"cik": 1423053, "name": "Citadel Advisors LLC",              "short": "Citadel",        "tier": "S", "manager": "Ken Griffin",         "style": "quant"},
    {"cik": 1167483, "name": "Tiger Global Management LLC",       "short": "Tiger Global",   "tier": "S", "manager": "Chase Coleman",       "style": "picker"},
    {"cik": 1135730, "name": "Coatue Management LLC",             "short": "Coatue",         "tier": "S", "manager": "Philippe Laffont",    "style": "picker"},
    {"cik": 1061165, "name": "Lone Pine Capital LLC",             "short": "Lone Pine",      "tier": "S", "manager": "Stephen Mandel",      "style": "picker"},
    {"cik": 1103804, "name": "Viking Global Investors LP",        "short": "Viking",         "tier": "S", "manager": "Andreas Halvorsen",   "style": "picker"},
    {"cik":  934639, "name": "Maverick Capital Ltd",              "short": "Maverick",       "tier": "S", "manager": "Lee Ainslie",         "style": "picker"},
    {"cik": 1387322, "name": "Whale Rock Capital Management LLC", "short": "Whale Rock",     "tier": "S", "manager": "Alex Sacerdote",      "style": "picker"},
    {"cik": 1138995, "name": "Glenview Capital Management LLC",   "short": "Glenview",       "tier": "S", "manager": "Larry Robbins",       "style": "picker"},
    {"cik": 1345471, "name": "Trian Fund Management LP",          "short": "Trian",          "tier": "S", "manager": "Nelson Peltz",        "style": "activist"},
    {"cik": 1517137, "name": "Starboard Value LP",                "short": "Starboard",      "tier": "S", "manager": "Jeffrey Smith",       "style": "activist"},
    {"cik":  921669, "name": "Icahn Carl C",                      "short": "Icahn",          "tier": "S", "manager": "Carl Icahn",          "style": "activist"},
    {"cik": 1351069, "name": "ValueAct Capital Management LP",    "short": "ValueAct",       "tier": "S", "manager": "Mason Morfit",        "style": "activist"},
    {"cik": 1998597, "name": "JANA Partners Management LP",       "short": "JANA",           "tier": "S", "manager": "Barry Rosenstein",    "style": "activist"},
    {"cik": 1541617, "name": "Altimeter Capital Management LP",   "short": "Altimeter",      "tier": "S", "manager": "Brad Gerstner",       "style": "picker"},
    {"cik": 1603466, "name": "Point72 Asset Management LP",       "short": "Point72",        "tier": "S", "manager": "Steve Cohen",         "style": "quant"},
    {"cik": 1009207, "name": "D. E. Shaw & Co Inc",               "short": "D.E. Shaw",      "tier": "S", "manager": "Quant",               "style": "quant"},
    {"cik": 1179392, "name": "Two Sigma Investments LP",          "short": "Two Sigma",      "tier": "S", "manager": "Quant",               "style": "quant"},
    {"cik": 1350694, "name": "Bridgewater Associates LP",         "short": "Bridgewater",    "tier": "S", "manager": "Ray Dalio (founder)", "style": "quant"},
    {"cik": 1167557, "name": "AQR Capital Management LLC",        "short": "AQR",            "tier": "S", "manager": "Cliff Asness",        "style": "quant"},
    {"cik": 1273087, "name": "Millennium Management LLC",         "short": "Millennium",     "tier": "S", "manager": "Izzy Englander",      "style": "quant"},
    # --- Tier A — active alpha-seeking managers --------------------------
    {"cik": 1422848, "name": "Capital Research Global Investors", "short": "Capital Research","tier": "A", "manager": "Capital Group",      "style": "picker"},
    {"cik": 1422849, "name": "Capital World Investors",           "short": "Capital World",  "tier": "A", "manager": "Capital Group",       "style": "picker"},
    {"cik":  902219, "name": "Wellington Management Group LLP",   "short": "Wellington",     "tier": "A", "manager": "",                    "style": "picker"},
    {"cik":  315066, "name": "FMR LLC",                           "short": "Fidelity (FMR)", "tier": "A", "manager": "incl. Contrafund",    "style": "picker"},
    {"cik":   80255, "name": "T. Rowe Price Associates Inc",      "short": "T. Rowe Price",  "tier": "A", "manager": "(active funds)",      "style": "picker"},
    {"cik": 1088875, "name": "Baillie Gifford & Co",              "short": "Baillie Gifford","tier": "A", "manager": "Scottish growth",     "style": "picker"},
    {"cik": 1020066, "name": "Sands Capital Management LLC",      "short": "Sands Capital",  "tier": "A", "manager": "",                    "style": "picker"},
    {"cik": 1034524, "name": "Polen Capital Management LLC",      "short": "Polen",          "tier": "A", "manager": "",                    "style": "picker"},
    {"cik":  200217, "name": "Dodge & Cox",                       "short": "Dodge & Cox",    "tier": "A", "manager": "",                    "style": "picker"},
    {"cik":  763212, "name": "Primecap Management Co",            "short": "Primecap",       "tier": "A", "manager": "",                    "style": "picker"},
    {"cik":  945631, "name": "Eagle Capital Management LLC",      "short": "Eagle Capital",  "tier": "A", "manager": "Meryl Witmer",        "style": "picker"},
    {"cik":  936753, "name": "Ariel Investments LLC",             "short": "Ariel",          "tier": "A", "manager": "John Rogers",         "style": "picker"},
]

TIER_WEIGHT = {"S": 3.0, "A": 2.0}  # mirrors fundTiers.ts


def all_funds() -> List[Fund]:
    return list(FUNDS)


def fund_by_cik(cik: int) -> Optional[Fund]:
    for f in FUNDS:
        if f["cik"] == int(cik):
            return f
    return None
