"""Broad ETF universe for SEPA.

The Russell holdings files (`universe.py`) are *equities only* — iShares'
Holdings export is filtered to Asset Class == Equity, which drops the cash /
futures / fund-of-fund rows. So ETFs never entered the SEPA scan from that
path.

This module supplies a separate, hand-maintained list of liquid US-listed
ETFs so the user's "ETFs should come up in SEPA too" request is satisfied
(2026-05-30). It's intentionally BROAD (hundreds) per the user's choice —
SEPA's own liquidity gate + trend template do the real filtering downstream,
so an over-inclusive list is fine: thin/odd funds just never become
candidates. A few stale tickers are harmless (the data provider returns
nothing → the symbol is silently dropped).

Maintenance: this is a static list. ETFs launch/close slowly relative to the
quarterly Russell refresh, so an occasional manual top-up is enough. Keep it
alphabetised within each category block for easy diffing.

NOTE on leveraged/inverse funds: they're included because the user asked for
the broad set, and several (TQQQ, SOXL, FNGU, etc.) trend hard and are real
swing vehicles. They carry decay risk and can dominate momentum sorts — the
ETF type filter on the SEPA page lets the user exclude them when wanted.
"""
from __future__ import annotations

# ── Broad market / total market / style ─────────────────────────────────
_BROAD = [
    "SPY", "VOO", "IVV", "VTI", "ITOT", "SCHB", "SCHX", "QQQ", "QQQM",
    "DIA", "IWB", "IWV", "IWM", "IWR", "IJH", "IJR", "VB", "VO", "MDY",
    "RSP", "SPLG", "SPTM", "MGC", "MGK", "MGV", "OEF", "SPYG", "SPYV",
    "VTV", "VUG", "IWF", "IWD", "IVW", "IVE", "VBR", "VBK", "VOE", "VOT",
]

# ── International / regions / single country ─────────────────────────────
_INTL = [
    "VEA", "VWO", "EFA", "EEM", "IEFA", "IEMG", "ACWI", "VT", "VXUS",
    "VGK", "VPL", "SCHF", "SCHE", "IXUS", "EWJ", "EWZ", "EWG", "EWU",
    "EWY", "EWT", "EWH", "EWC", "EWA", "EWW", "EWP", "EWI", "EWQ", "EWL",
    "EWD", "EWN", "EWS", "EWM", "EZU", "FXI", "MCHI", "KWEB", "ASHR",
    "CQQQ", "INDA", "INDY", "EPI", "SMIN", "EIDO", "THD", "TUR", "EZA",
    "EPOL", "ARGT", "ILF", "GXG", "ECH", "VNM", "EWZS",
]

# ── Sectors (SPDR / Vanguard / Fidelity) ────────────────────────────────
_SECTOR = [
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE",
    "XLC", "VGT", "VHT", "VFH", "VDE", "VIS", "VCR", "VDC", "VPU", "VAW",
    "VNQ", "VOX", "FTEC", "FHLC", "FNCL", "FENY", "FIDU", "FDIS", "FSTA",
    "FUTY", "FMAT", "FREL", "FCOM", "IYW", "IYF", "IYH", "IYE", "IYJ",
    "IYC", "IYK", "IDU", "IYM", "IYR", "IYZ",
]

# ── Tech / semis / software / internet / robotics / cyber ───────────────
_TECH = [
    "SMH", "SOXX", "XSD", "PSI", "IGV", "SKYY", "WCLD", "CLOU", "FDN",
    "IGM", "ARKK", "ARKW", "ARKF", "ARKQ", "ARKG", "ARKX", "BOTZ", "ROBO",
    "IRBO", "BUG", "CIBR", "HACK", "FINX", "IPAY", "SNSR", "FIVG", "NXTG",
    "METV", "ESPO", "HERO", "GAMR", "QTUM", "AIQ", "ROBT", "XT", "XITK",
]

# ── Biotech / healthcare innovation ─────────────────────────────────────
_HEALTH = [
    "XBI", "IBB", "GNOM", "SBIO", "PPH", "IHI", "IHF", "XHE", "XHS",
    "XPH", "FBT", "BBH", "IDNA", "HELX", "ARKG",
]

# ── Energy / metals / commodities / materials / clean energy ────────────
_COMMOD = [
    "XOP", "OIH", "IEO", "IEZ", "AMLP", "MLPX", "FCG", "USO", "BNO",
    "UNG", "UGA", "GLD", "IAU", "GLDM", "SGOL", "SLV", "SIVR", "PPLT",
    "PALL", "GDX", "GDXJ", "SIL", "SILJ", "COPX", "URA", "URNM", "NLR",
    "LIT", "REMX", "DBC", "DBA", "PDBC", "GUNR", "WOOD", "MOO", "TAN",
    "ICLN", "PBW", "FAN", "QCLN", "ACES", "KWT", "WEAT", "CORN", "SOYB",
]

# ── Industrials / defense / transport / infrastructure ──────────────────
_INDUSTRIAL = [
    "ITA", "PPA", "XAR", "JETS", "IYT", "XTN", "PAVE", "GRID", "IFRA",
]

# ── Consumer / retail / homebuilders ────────────────────────────────────
_CONSUMER = [
    "XRT", "XHB", "ITB", "PEJ", "IBUY", "ONLN", "FTXD", "BETZ", "EATZ",
]

# ── Real estate ─────────────────────────────────────────────────────────
_REIT = [
    "SCHH", "REZ", "REM", "MORT", "INDS", "ICF", "RWR", "USRT", "REET",
]

# ── Dividend / factor / smart-beta ──────────────────────────────────────
_FACTOR = [
    "VIG", "VYM", "SCHD", "DVY", "NOBL", "SDY", "HDV", "DGRO", "SPHD",
    "DLN", "MTUM", "QUAL", "USMV", "SPLV", "VLUE", "SIZE", "DGRW", "MOAT",
    "COWZ", "FNDX", "PRF", "RPV", "RPG", "QQEW", "FFTY",
]

# ── Bonds / treasuries / credit (major, liquid) ─────────────────────────
_BONDS = [
    "TLT", "IEF", "SHY", "IEI", "GOVT", "AGG", "BND", "BNDX", "LQD",
    "VCIT", "VCSH", "HYG", "JNK", "SJNK", "TIP", "VTIP", "MUB", "TFI",
    "EMB", "BKLN", "SHV", "BIL", "MBB", "TLH", "ZROZ", "EDV", "SGOV",
    "USHY", "ANGL",
]

# ── Crypto-adjacent ─────────────────────────────────────────────────────
_CRYPTO = [
    "BITO", "BITX", "IBIT", "FBTC", "ARKB", "BITB", "HODL", "ETHE",
    "GBTC", "ETHA", "BLOK", "DAPP", "BKCH", "WGMI", "BITQ",
]

# ── Leveraged / inverse (broad index + sector) ──────────────────────────
_LEVERAGED = [
    "TQQQ", "SQQQ", "SPXL", "SPXS", "UPRO", "SPXU", "SDOW", "UDOW",
    "TNA", "TZA", "QLD", "QID", "SSO", "SDS", "FAS", "FAZ", "LABU",
    "LABD", "SOXL", "SOXS", "NUGT", "DUST", "TMF", "TMV", "YINN", "YANG",
    "TECL", "TECS", "FNGU", "FNGD", "BULZ", "WEBL", "DRN", "DRV", "ERX",
    "ERY", "GUSH", "DRIP", "JNUG", "JDST", "BOIL", "KOLD",
]

# ── Volatility ──────────────────────────────────────────────────────────
_VOL = ["VXX", "UVXY", "SVXY", "VIXY", "UVIX"]


_ALL_BLOCKS = [
    _BROAD, _INTL, _SECTOR, _TECH, _HEALTH, _COMMOD, _INDUSTRIAL,
    _CONSUMER, _REIT, _FACTOR, _BONDS, _CRYPTO, _LEVERAGED, _VOL,
]


def etf_universe() -> list[str]:
    """Deduplicated, order-preserving broad ETF list (~300 tickers)."""
    out: list[str] = []
    seen: set[str] = set()
    for block in _ALL_BLOCKS:
        for t in block:
            u = t.strip().upper()
            if u and u not in seen:
                seen.add(u)
                out.append(u)
    return out


# Convenience constant for callers that just want the count / membership.
ETF_UNIVERSE: list[str] = etf_universe()
