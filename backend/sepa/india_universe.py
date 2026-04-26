"""Indian stock universe — Nifty 50 hardcoded list.

Each entry maps an NSE ticker to:
  - name: full legal/marketing name (used for ValuePickr + MoneyControl search)
  - slug: lowercase-hyphenated form for MoneyControl URL paths
  - aliases: alternative search terms that retail users actually type on Reddit

Why hardcoded vs fetched:
  Nifty 50 changes a couple times a year via official NSE rebalancing — it's
  not a moving target like sector ETF holdings. A 2-line manual update
  beats a brittle scrape of the NSE site (which actively fights bots and
  needs a session cookie). Refresh this list when NSE announces a
  rebalance — see https://www.nseindia.com/products-services/indices-niftynext50-index.

Last verified: late 2025 — TRENT and SHRIRAMFIN added in the latest rebalance.
"""
from __future__ import annotations


NIFTY_50: list[dict] = [
    {"symbol": "RELIANCE",   "name": "Reliance Industries",          "slug": "reliance-industries",                     "aliases": ["Reliance"]},
    {"symbol": "TCS",        "name": "Tata Consultancy Services",    "slug": "tata-consultancy-services",                "aliases": ["TCS"]},
    {"symbol": "HDFCBANK",   "name": "HDFC Bank",                    "slug": "hdfc-bank",                                "aliases": ["HDFC"]},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel",                "slug": "bharti-airtel",                            "aliases": ["Airtel"]},
    {"symbol": "ICICIBANK",  "name": "ICICI Bank",                   "slug": "icici-bank",                               "aliases": ["ICICI"]},
    {"symbol": "INFY",       "name": "Infosys",                      "slug": "infosys",                                  "aliases": ["Infy"]},
    {"symbol": "SBIN",       "name": "State Bank of India",          "slug": "state-bank-india",                         "aliases": ["SBI"]},
    {"symbol": "LT",         "name": "Larsen & Toubro",              "slug": "larsen-toubro",                            "aliases": ["L&T"]},
    {"symbol": "ITC",        "name": "ITC",                          "slug": "itc",                                      "aliases": []},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance",                "slug": "bajaj-finance",                            "aliases": []},
    {"symbol": "HINDUNILVR", "name": "Hindustan Unilever",           "slug": "hindustan-unilever",                       "aliases": ["HUL"]},
    {"symbol": "KOTAKBANK",  "name": "Kotak Mahindra Bank",          "slug": "kotak-mahindra-bank",                      "aliases": ["Kotak"]},
    {"symbol": "AXISBANK",   "name": "Axis Bank",                    "slug": "axis-bank",                                "aliases": ["Axis"]},
    {"symbol": "MARUTI",     "name": "Maruti Suzuki",                "slug": "maruti-suzuki-india",                      "aliases": ["Maruti"]},
    {"symbol": "M&M",        "name": "Mahindra & Mahindra",          "slug": "mahindra-mahindra",                        "aliases": ["Mahindra", "M&M"]},
    {"symbol": "SUNPHARMA",  "name": "Sun Pharmaceutical",           "slug": "sun-pharmaceutical-industries",            "aliases": ["Sun Pharma"]},
    {"symbol": "NTPC",       "name": "NTPC",                         "slug": "ntpc",                                     "aliases": []},
    {"symbol": "TITAN",      "name": "Titan Company",                "slug": "titan-company",                            "aliases": ["Titan"]},
    {"symbol": "HCLTECH",    "name": "HCL Technologies",             "slug": "hcl-technologies",                         "aliases": ["HCL Tech", "HCL"]},
    {"symbol": "ASIANPAINT", "name": "Asian Paints",                 "slug": "asian-paints",                             "aliases": ["Asian Paints"]},
    {"symbol": "ULTRACEMCO", "name": "UltraTech Cement",             "slug": "ultratech-cement",                         "aliases": ["UltraTech"]},
    {"symbol": "BAJAJ-AUTO", "name": "Bajaj Auto",                   "slug": "bajaj-auto",                               "aliases": ["Bajaj Auto"]},
    {"symbol": "ONGC",       "name": "Oil and Natural Gas Corporation","slug": "oil-natural-gas-corporation",            "aliases": ["ONGC"]},
    {"symbol": "JSWSTEEL",   "name": "JSW Steel",                    "slug": "jsw-steel",                                "aliases": ["JSW"]},
    {"symbol": "ADANIPORTS", "name": "Adani Ports and SEZ",          "slug": "adani-ports-special-economic-zone",        "aliases": ["Adani Ports"]},
    {"symbol": "COALINDIA",  "name": "Coal India",                   "slug": "coal-india",                               "aliases": []},
    {"symbol": "TATAMOTORS", "name": "Tata Motors",                  "slug": "tata-motors",                              "aliases": ["Tata Motors"]},
    {"symbol": "POWERGRID",  "name": "Power Grid Corporation",       "slug": "power-grid-corporation-india",             "aliases": ["PowerGrid"]},
    {"symbol": "WIPRO",      "name": "Wipro",                        "slug": "wipro",                                    "aliases": []},
    {"symbol": "NESTLEIND",  "name": "Nestle India",                 "slug": "nestle-india",                             "aliases": ["Nestle"]},
    {"symbol": "INDUSINDBK", "name": "IndusInd Bank",                "slug": "indusind-bank",                            "aliases": ["IndusInd"]},
    {"symbol": "GRASIM",     "name": "Grasim Industries",            "slug": "grasim-industries",                        "aliases": ["Grasim"]},
    {"symbol": "HDFCLIFE",   "name": "HDFC Life Insurance",          "slug": "hdfc-life-insurance",                      "aliases": ["HDFC Life"]},
    {"symbol": "TATASTEEL",  "name": "Tata Steel",                   "slug": "tata-steel",                               "aliases": ["Tata Steel"]},
    {"symbol": "SBILIFE",    "name": "SBI Life Insurance",           "slug": "sbi-life-insurance",                       "aliases": ["SBI Life"]},
    {"symbol": "HINDALCO",   "name": "Hindalco Industries",          "slug": "hindalco-industries",                      "aliases": ["Hindalco"]},
    {"symbol": "BAJAJFINSV", "name": "Bajaj Finserv",                "slug": "bajaj-finserv",                            "aliases": ["Bajaj Finserv"]},
    {"symbol": "BPCL",       "name": "Bharat Petroleum",             "slug": "bharat-petroleum-corporation",             "aliases": ["BPCL"]},
    {"symbol": "EICHERMOT",  "name": "Eicher Motors",                "slug": "eicher-motors",                            "aliases": ["Eicher", "Royal Enfield"]},
    {"symbol": "ADANIENT",   "name": "Adani Enterprises",            "slug": "adani-enterprises",                        "aliases": ["Adani"]},
    {"symbol": "CIPLA",      "name": "Cipla",                        "slug": "cipla",                                    "aliases": []},
    {"symbol": "BRITANNIA",  "name": "Britannia Industries",         "slug": "britannia-industries",                     "aliases": ["Britannia"]},
    {"symbol": "DRREDDY",    "name": "Dr. Reddy's Laboratories",     "slug": "dr-reddys-laboratories",                   "aliases": ["Dr Reddy", "Dr. Reddy's"]},
    {"symbol": "TECHM",      "name": "Tech Mahindra",                "slug": "tech-mahindra",                            "aliases": ["Tech Mahindra"]},
    {"symbol": "DIVISLAB",   "name": "Divi's Laboratories",          "slug": "divis-laboratories",                       "aliases": ["Divis Lab"]},
    {"symbol": "APOLLOHOSP", "name": "Apollo Hospitals",             "slug": "apollo-hospitals-enterprise",              "aliases": ["Apollo"]},
    {"symbol": "HEROMOTOCO", "name": "Hero MotoCorp",                "slug": "hero-motocorp",                            "aliases": ["Hero"]},
    {"symbol": "TATACONSUM", "name": "Tata Consumer Products",       "slug": "tata-consumer-products",                   "aliases": ["Tata Consumer"]},
    {"symbol": "TRENT",      "name": "Trent",                        "slug": "trent",                                    "aliases": ["Westside"]},
    {"symbol": "SHRIRAMFIN", "name": "Shriram Finance",              "slug": "shriram-finance",                          "aliases": ["Shriram"]},
    {"symbol": "JIOFIN",     "name": "Jio Financial Services",       "slug": "jio-financial-services",                   "aliases": ["Jio Financial"]},
]


_BY_SYMBOL: dict[str, dict] = {row["symbol"]: row for row in NIFTY_50}


def get(symbol: str) -> dict | None:
    """Lookup a Nifty 50 entry by NSE ticker."""
    return _BY_SYMBOL.get(symbol.upper())


def all_symbols() -> list[str]:
    return [row["symbol"] for row in NIFTY_50]


def search_terms_for(symbol: str) -> list[str]:
    """Build the search-term list for forum scrapers.

    Order matters: most-specific first (the ticker), then full company name,
    then retail aliases. Scrapers can de-dupe results across queries.
    """
    row = get(symbol)
    if not row:
        return [symbol]
    terms = [row["symbol"], row["name"]]
    terms.extend(row.get("aliases") or [])
    # de-dupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        k = t.lower()
        if k in seen or not t:
            continue
        seen.add(k)
        out.append(t)
    return out
