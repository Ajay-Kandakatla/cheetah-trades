"""Symbol identity — renames, former names, and per-provider spelling.

Ajay 2026-08-16, looking at EchoStar: *"look at this issue with SATS stocks"*.
The page said **"SATS looks delisted or acquired."** SATS was trading at $91.89
that morning. Two separate defects were producing that one wrong sentence, and
both of them make a live company look dead:

**1. Ticker renames.** EchoStar renamed SATS → ECHO effective 2026-06-24. Our
price frame for SATS ends 2026-06-23 and never resumes, so ``is_stale`` fires
and the UI asserts the company was acquired. Block did the same thing in January
2025 (SQ → XYZ) and **that one has been silently wrong for 576 days** — the app
has been showing a dead SQ this whole time.

**2. Provider spelling for class shares.** Massive serves ``BRK.B``; our universe
spells it ``BRK-B`` (the S&P/Wikipedia convention). Massive returns *nothing* for
the dash form, so ``BRK-B``, ``BF-B`` and ``MOG-A`` have all been quietly served
by the **yfinance fallback** — different provider, different adjustment
convention, same scan. ``CWEN-A`` fails on both spellings at both providers, so
it vanished from the universe entirely.

WHY THE RENAME MAP IS CURATED, NOT INFERRED
-------------------------------------------
It is tempting to detect a rename automatically: data stops, so go look for a
symbol that started trading the same week at a similar price. **Do not.** A wrong
guess splices another company's price history into a chart Ajay sizes real
positions against, and it would do so silently. Every entry here is hand-checked
against both providers and carries the evidence. A missing entry costs one stale
name that the staleness monitor will flag; a wrong entry costs a fabricated
chart. Those are not symmetric.

Nothing in Minervini covers this. It is data plumbing.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("sepa.symbols")

# ---------------------------------------------------------------------------
# Ticker renames
# ---------------------------------------------------------------------------
# {OLD: (NEW, first_session_under_the_new_symbol, evidence)}
#
# `effective` is the first session that PRINTS under the new symbol, so the old
# series is kept strictly before it. Verified 2026-08-16 by fetching both symbols
# from Massive and checking the boundary bars are consecutive sessions with a
# continuous price.
RENAMES: dict[str, tuple[str, str, str]] = {
    "SATS": ("ECHO", "2026-06-24",
             "EchoStar Corp. SATS last bar 2026-06-23 close 103.915; ECHO first "
             "bar 2026-06-24 open 101.16. Consecutive sessions, -2.6% overnight, "
             "no split."),
    "SQ": ("XYZ", "2025-01-21",
           "Block, Inc. SQ last bar 2025-01-17 close 86.96; XYZ first bar "
           "2025-01-21 open 88.06 (2025-01-20 was MLK Day). Consecutive "
           "sessions, no split."),
    "DOOO": ("DOO", "2025-12-08",
             "BRP Inc. DOOO last bar 2025-12-05 close 76.66; DOO first bar "
             "2025-12-08 open 81.67. Consecutive sessions (Fri->Mon), +6.5% "
             "overnight, no split. Massive reference 2026-08-25: DOO active "
             "on XNAS as 'BRP Inc. Common Subordinate Voting Shares'; DOOO "
             "NOT_FOUND."),
    "IAC": ("PPLI", "2026-06-04",
            "IAC renamed to People Inc. IAC last bar 2026-06-03 close 42.24; "
            "PPLI first bar 2026-06-04 open 42.72. Consecutive sessions, "
            "+1.1% overnight, no split. Massive reference 2026-08-25: PPLI "
            "active on XNAS as 'People Incorporated Common Stock'; IAC "
            "NOT_FOUND."),
    # The FIRST entry in this file whose boundary-bar check could not be run.
    # Read the PARTIAL EVIDENCE sentence before copying this shape.
    "ZI": ("GTM", "2025-05-13",
           "ZoomInfo Technologies. EFFECTIVE DATE SOURCE: our own price_cache, "
           "NOT a provider list_date. The 2y window reaches 2024-09-16 for "
           "every comparison name (NET/ECHO/XYZ/PPLI all 503 bars from "
           "2024-09-16) and GTM's series starts 2025-05-13 with nothing before "
           "it — eight months INSIDE the window, so that is the first session "
           "printing under GTM, not a window edge. Massive reference "
           "2026-09-18: GTM active on XNAS as 'ZoomInfo Technologies Inc "
           "Common Stock'; ZI NOT_FOUND. Its list_date 2020-06-04 is "
           "ZoomInfo's ORIGINAL IPO and was deliberately NOT written here — a "
           "reference list_date for a renamed security is the old listing, and "
           "main.py renders `effective` to Ajay verbatim. PARTIAL EVIDENCE: "
           "the usual boundary check (last ZI bar, consecutive session, "
           "continuous price) COULD NOT BE RUN — there is no ZI series at "
           "either provider and no ZI companies doc. Prophylactic: ZI is in no "
           "universe component today, so this heals nothing yet. COST: "
           "former_names('GTM') now returns ['ZI'], so prices._fetch spends "
           "one dead Massive miss plus one dead yfinance call per UNCACHED GTM "
           "load — see sepa/prices.py _fetch and _fetch_one. CACHE_TTL_SEC is "
           "20h, so that is roughly one wasted pair per day, not per scan, "
           "plus the three force=True callers. splice_history returns the new "
           "frame on an empty old, so nothing crashes and nothing corrupts."),
    # --- 2026-09-29 dead-ticker triage (Ajay: "Remove the dead ones please").
    # Each verified against Massive live 2026-09-29: old symbol reference
    # NOT_FOUND, successor active with the SAME CIK (and composite FIGI unless
    # noted) plus a ticker_change event on `effective`; boundary bars are
    # consecutive sessions inside SPLICE_MAX_JUMP_RATIO / SPLICE_MAX_GAP_DAYS.
    # VSCO -> VSXY is NOT here: +44.6% at the boundary open fails the splice
    # guard, so it is HIS CALL (docs/sepa/symbol_fates_audit.md).
    "BBBY": ("NXH", "2026-08-17",
             "Bed Bath & Beyond, Inc. (ex-Overstock/Beyond) renamed "
             "Neighborhood Intelligence, Inc. Same CIK 0001130713 and FIGI "
             "BBG000BF7BV7; NXH events OSTK->BYON->BBBY->NXH. BBBY last bar "
             "2026-08-14 close 4.35; NXH first bar 2026-08-17 open 4.55. "
             "Consecutive sessions (Fri->Mon), +4.6% overnight, no split."),
    "BITF": ("KEEL", "2026-04-06",
             "Bitfarms Ltd. rebranded Keel Infrastructure Corp. on its U.S. "
             "redomicile (GlobeNewswire 2026-02-06). Same CIK 0001812477; "
             "composite FIGI changed with the redomicile. BITF last bar "
             "2026-04-02 close 1.98 (04-03 Good Friday); KEEL first bar "
             "2026-04-06 open 2.07. Consecutive sessions, +4.5% overnight, "
             "no split."),
    "EQR": ("VMRK", "2026-08-18",
            "Equity Residential renamed Vivmark Residential after the "
            "AvalonBay merger (EQR surviving; Benzinga 2026-05-21). Same "
            "FIGI BBG000BG8M31, and VMRK's ticker events run EQR (2003-09-10) "
            "-> VMRK (2026-08-18). CIK differs: the inactive EQR record "
            "carries 0000931182 (ERP Operating LP, the operating-partnership "
            "record), VMRK carries 0000906107. EQR last bar 2026-08-17 close "
            "63.66; VMRK first bar 2026-08-18 open 64.16. Consecutive "
            "sessions, +0.8% overnight, no split."),
    "FDP": ("DMC", "2026-06-29",
            "Fresh Del Monte Produce renamed Del Monte Corporation. Same CIK "
            "0001047340; DMC events FDP->DMC 2026-06-29. FDP last bar "
            "2026-06-26 close 29.22; DMC first bar 2026-06-29 open 29.00. "
            "Consecutive sessions (Fri->Mon), -0.75% overnight, no split."),
    "HLX": ("HOS", "2026-09-02",
            "Helix Energy Solutions renamed Hornbeck Offshore Services after "
            "the Hornbeck merger (Helix surviving; Benzinga 2026-04-23). Same "
            "CIK 0000866829 and FIGI BBG000J7Q1L9. HLX last bar 2026-09-01 "
            "close 10.60; HOS first bar 2026-09-02 open 10.83. Consecutive "
            "sessions, +2.2% overnight, no split."),
    "LC": ("HAPN", "2026-06-22",
           "LendingClub Corporation renamed Happen, Inc. (Motley Fool "
           "2026-05-13). Same CIK 0001409970 and FIGI BBG001YKDND6. LC last "
           "bar 2026-06-18 close 19.21; HAPN first bar 2026-06-22 open 19.40 "
           "(06-19 Juneteenth). Consecutive sessions, +1.0% overnight, no "
           "split."),
    "SCVL": ("SHOE", "2026-06-12",
             "Shoe Carnival Inc renamed Shoe Station Group, Inc. (Investing.com "
             "2026-03-27). Same CIK 0000895447 and FIGI BBG000BF4DG3. SCVL "
             "last bar 2026-06-11 close 17.43; SHOE first bar 2026-06-12 open "
             "17.43. Consecutive sessions, 0.0% overnight, no split."),
    # --- 2026-09-29 Dual Momentum data audit: TICKER REUSE + RENAME ----------
    # HIS CALL #6: these two entries ship ONLY together with the one-time
    # refetch `load_prices("BNY", force=True)` / `("GOLD", force=True)` in the
    # same promote. Without the refetch the read-time cut
    # (prices._cut_foreign_head) leaves BNY ~90 bars and GOLD ~208 bars in
    # every load_prices / bulk_cached_frames read app-wide. If he says no,
    # delete this block and the tests marked "RENAMES hunk" in
    # tests/test_foreign_head_cut_2026_09_29.py; FIRST_SESSION stays.
    "BK": ("BNY", "2026-05-21",
           "Bank of New York Mellon renamed BK -> BNY. Same FIGI "
           "BBG000BD8PN9 across both symbols; Massive ticker event "
           "2026-05-21 BK->BNY and the inactive BK listing shows "
           "delisted_utc 2026-05-21. BK last bar 2026-05-20 close 137.16; "
           "BNY first bar 2026-05-21 open 136.46. Consecutive sessions, "
           "-0.5% overnight, no split (splice ratio 1.005, 1-day gap). "
           "Massive's BNY frame BEFORE 2026-05-21 is a DIFFERENT security: "
           "BlackRock New York Municipal Income Trust (FUND, FIGI "
           "BBG000BZF6G2, ~$10) to 2026-02-06, then a 104-day hole — that "
           "reused-ticker head gave BNY a fake +1,435% 12m on the Dual "
           "Momentum page. Verified 2026-09-29 (scratchpad dm_audit.py)."),
    "AMRK": ("GOLD", "2025-12-02",
             "A-Mark Precious Metals renamed to Gold.com, AMRK -> GOLD. FIGI "
             "BBG005ZVDK48; Massive ticker event 2025-12-02. AMRK last bar "
             "2025-12-01 close 29.25; GOLD first bar 2025-12-02 open 30.13. "
             "Consecutive sessions, +3.0% overnight, no split. The GOLD frame "
             "BEFORE that is a DIFFERENT security: Barrick (FIGI "
             "BBG000BB07P9) to 2025-05-08 close 18.86, then a 208-day hole; "
             "Barrick has traded as `B` since 2025-05-09. Verified "
             "2026-09-29 (scratchpad dm_audit sweep)."),
    # --- end 2026-09-29 RENAMES block ----------------------------------------
    # --- 2026-09-29 Russell holdings refresh: a rename the live IWV list shows.
    "DOMO": ("HUCK", "2026-09-24",
             "Domo, Inc. renamed Huckleberry.ai, Inc. Same CIK 0001505952 and "
             "composite FIGI BBG00L2NS0B7 (both Class B); Massive ticker "
             "events DOMO 2018-06-29 -> HUCK 2026-09-24; DOMO reference "
             "NOT_FOUND, its inactive record delisted_utc 2026-09-24. DOMO "
             "last bar 2026-09-23 close 3.55; HUCK first bar 2026-09-24 open "
             "3.45. Consecutive sessions, -2.8% overnight, no split. The live "
             "iShares IWV/IWC holdings (as of 2026-09-28) list HUCK. Verified "
             "2026-09-29 against Massive live."),
    # --- 2026-10-07 missing-data audit (docs/sepa/missing_data_audit_2026_10_07.md)
    "MODG": ("CALY", "2026-01-16",
             "Topgolf Callaway Brands renamed Callaway Golf Company, MODG -> "
             "CALY. Same composite FIGI BBG000CPCVY1 and same CIK 0000837465 on "
             "both Massive reference records; MODG inactive, delisted_utc "
             "2026-01-16. CALY first Massive bar 2026-01-16 open 14.81 (the "
             "cached CALY frame before that is a DIFFERENT security, a $50 fund, "
             "to 2025-09-30, then a hole). Yahoo's continuous series under CALY: "
             "2026-01-15 close 14.68 -> 2026-01-16 open 14.81, consecutive "
             "sessions, +0.9% overnight, no split. Verified 2026-10-07 "
             "(scratchpad data_audit fates_evidence / modg_yf)."),
}

# Reverse index, built once. A current symbol can have more than one former name
# over a long enough history, so the value is a list, oldest first.
_FORMER: dict[str, list[str]] = {}
for _old, (_new, _eff, _why) in RENAMES.items():
    _FORMER.setdefault(_new.upper(), []).append(_old.upper())


def resolve(symbol: str) -> str:
    """The symbol that trades TODAY. ``SATS`` → ``ECHO``. PURE.

    Idempotent, and safe on a symbol that was never renamed. Chains are not
    followed on purpose: a two-step rename should be written as a direct entry so
    the evidence stays readable.
    """
    if not symbol:
        return symbol
    s = symbol.strip().upper()
    entry = RENAMES.get(s)
    return entry[0] if entry else s


def former_names(symbol: str) -> list[str]:
    """Symbols this one used to trade under, oldest first. PURE."""
    if not symbol:
        return []
    return list(_FORMER.get(symbol.strip().upper(), []))


def rename_of(symbol: str) -> Optional[dict]:
    """Rename record for an OLD symbol, or None. PURE.

    The UI reads this to say "SATS now trades as ECHO" instead of claiming the
    company was acquired.
    """
    entry = RENAMES.get((symbol or "").strip().upper())
    if not entry:
        return None
    new, eff, why = entry
    return {"from": symbol.strip().upper(), "to": new, "effective": eff,
            "evidence": why}


# ---------------------------------------------------------------------------
# Delistings — names that no longer trade ANYWHERE, under ANY spelling
# ---------------------------------------------------------------------------
# {SYMBOL: evidence}. Curated for the same reason RENAMES is: a wrong removal
# hides a live company, so every entry carries what was checked and when. A
# delisting is NOT a rename — there is no successor series to splice, so the
# symbol simply leaves the universe. If a successor is later discovered, move
# the entry to RENAMES with boundary-bar evidence.
#
# All verified 2026-08-25 against Massive: reference lookup NOT_FOUND (both
# spellings for class shares), zero daily aggs 2026-08-08..2026-08-25, and an
# active-listings name search that found no successor. Most carry the classic
# deal-close signature: price pinned at the deal level for days, then a final
# session on a multiple of average volume.
DELISTED: dict[str, str] = {
    "SMAR": "Smartsheet. Last bar 2025-01-21, pinned $56.4x for days, final "
            "session 6x volume — take-private close. Sat dead in the universe "
            "for 19 months (the SQ lesson, again).",
    "CFLT": "Confluent. Last bar 2026-03-16, pinned ~$30.7, final session "
            "~4x volume — acquisition close.",
    "CWEN-A": "Clearway Energy Class A. Last bar 2026-04-30. NOT_FOUND as "
              "CWEN-A and CWEN.A; CWEN (Class C) remains active on XNYS — "
              "the A class was retired, not renamed.",
    "MASI": "Masimo. Last bar 2026-06-09, pinned $179.9x, final session 3x "
            "volume — acquisition close.",
    "BLD": "TopBuild. Last bar 2026-06-30 after a two-day -15% slide; no "
           "successor listing found by name search.",
    "JHG": "Janus Henderson Group. Last bar 2026-06-30, pinned $51.9x, final "
           "session 3x volume — acquisition close (only ETF products carry "
           "the Janus Henderson name now).",
    "NSA": "National Storage Affiliates. Last bar 2026-07-21, final session "
           "13x volume — acquisition close.",
    "EA": "Electronic Arts. Last bar 2026-08-04, pinned $209.9x, final "
          "session 10x volume — take-private close.",
    "AVB": "AvalonBay Communities. Last bar 2026-08-14; reference NOT_FOUND, "
           "no successor by name search. No deal-close pin — likely a "
           "stock-for-stock merger; revisit if a successor surfaces. "
           "2026-09-29: the acquirer surfaced — AvalonBay merged into EQR, "
           "which became VMRK. VMRK is the ACQUIRER, a different issuer, not "
           "a successor to splice; AVB stays DELISTED.",
    "GFRR": "Never in the universe — a ghost in Massive's movers snapshot "
            "that erred the catalysts cron every 5 minutes. Reference "
            "NOT_FOUND, zero aggs, Yahoo 404s the quote.",
    # --- 2026-09-29 dead-ticker triage (Ajay: "Remove the dead ones please").
    # The latest SEPA scan skipped these as stale / no price data. Verified
    # 2026-09-29 against Massive live: reference NOT_FOUND, an inactive record
    # with delisted_utc, no daily aggs after the last bar through 2026-09-29,
    # no same-CIK or by-name active successor. An acquirer that keeps its own
    # series (MBC, AVO, OCFC, CHTR, IONQ ...) is NOT a splice.
    "ADRO": "Aduro Biotech -> Chinook (KDNY, same CIK, delisted 2023-08-14). "
            "ADRO delisted 2020-10-06; the iShares row is an unlisted Chinook "
            "CVR marked NO MARKET. No active ticker under the CIK.",
    "AKE": "Akero Therapeutics CVR — an iShares R3000 row, never a tradeable "
           "equity. Parent AKRO delisted 2025-12-10 on the merger (Benzinga "
           "2025-11-18). No aggs, no cache frame.",
    "AMWD": "American Woodmark. Last bar 2026-05-27, delisted 2026-05-29 — "
            "stock-for-stock into MasterBrand (MBC keeps its own series; "
            "GlobeNewswire 2025-10-13).",
    "APGE": "Apogee Therapeutics. Last bar 2026-09-02, pinned $134.95-135.08, "
            "delisted 2026-09-04 — acquired by AbbVie (Motley Fool 2026-07-12).",
    "AVNS": "Avanos Medical. Last bar 2026-07-24, pinned $24.97-24.99, "
            "delisted 2026-07-28 — take-private (Benzinga 2026-04-14).",
    "CCRN": "Cross Country Healthcare. Last bar 2026-07-20, pinned "
            "$13.22-13.25, delisted 2026-07-22 — sold to Knox Lane "
            "(GlobeNewswire 2026-05-13).",
    "CEP": "Cantor Equity Partners (SPAC). Last bar 2025-12-08, delisted "
           "2025-12-09 — de-SPAC into XXI, a NEW issuer (different CIK, "
           "-24.7% boundary). Never splice SPAC-shell history.",
    "CPRX": "Catalyst Pharmaceuticals. Last bar 2026-07-14, pinned "
            "$31.47-31.49, delisted 2026-07-16 — acquired by Angelini Pharma "
            "(GlobeNewswire 2026-07-16).",
    "CRNX": "Crinetics Pharmaceuticals. Last bar 2026-08-31, pinned "
            "$84.78-84.95, delisted 2026-09-02 — acquired by Vertex (Motley "
            "Fool 2026-07-30).",
    "CVGW": "Calavo Growers. Last bar 2026-05-27, delisted 2026-05-29 — "
            "acquired by Mission Produce (AVO keeps its own series; "
            "GlobeNewswire 2026-05-28).",
    "CWAN": "Clearwater Analytics. Last bar 2026-06-24, pinned against the "
            "$24.55 buyout, delisted 2026-06-29 — take-private "
            "(GlobeNewswire 2026-03-30).",
    "ESPR": "Esperion Therapeutics. Last bar 2026-07-10, pinned $3.15-3.19, "
            "delisted 2026-07-14 — ARCHIMED buyout (Benzinga 2026-05-01).",
    "FFIC": "Flushing Financial. Last bar 2026-06-01 on 10x volume, delisted "
            "2026-06-02 — merged into OceanFirst (OCFC, different CIK; "
            "Benzinga 2026-04-27).",
    "GTLS": "Chart Industries. Last bar 2026-07-15, pinned against the $210 "
            "cash takeout, delisted 2026-07-17 — acquired by Baker Hughes "
            "(Benzinga 2025-07-29).",
    "GTXI": "GTx Inc. CVR — an iShares R3000/Micro-Cap row valued at $0.01, "
            "never a tradeable equity. GTx delisted 2019-06-10. No aggs, no "
            "cache frame.",
    "INH": "Inhibrx Inc CVR — an iShares R3000/Micro-Cap row, never a "
           "tradeable equity. Checked 2026-09-29: no Massive record at all. "
           "INBX is a separate "
           "entity (CIK 0002007919), not a successor.",
    "KALV": "KalVista Pharmaceuticals. Last bar 2026-06-10, pinned "
            "$26.95-27.00, delisted 2026-06-12 — cash acquisition "
            "(GlobeNewswire 2026-05-12 merger probe).",
    "KW": "Kennedy-Wilson Holdings. Last bar 2026-06-15 on 13x volume, "
          "delisted 2026-06-17 — Fairfax take-private (Benzinga 2026-06-16).",
    "LBRDA": "Liberty Broadband Class A. Last bar 2026-08-19 on 8.7x volume, "
             "delisted 2026-08-21 — absorbed by Charter (CHTR, different "
             "CIK; GlobeNewswire 2024-12-06).",
    "LBRDK": "Liberty Broadband Class C. Last bar 2026-08-19 on ~7x volume, "
             "delisted 2026-08-21 — absorbed by Charter (CHTR, different "
             "CIK; GlobeNewswire 2024-12-06).",
    "LEG": "Leggett & Platt. Last bar 2026-08-26 on 5-9x volume, delisted "
           "2026-08-27 — Somnigroup bid (Benzinga 2025-12-01); no completion "
           "release found, verdict rests on inactive + zero aggs since.",
    "LPRO": "Open Lending. Last bar 2026-07-29, pinned $3.14-3.15, delisted "
            "2026-07-31 — cash deal (GlobeNewswire 2026-06 merger probes).",
    "NFBK": "Northfield Bancorp. Last bar 2026-07-20, delisted 2026-07-21 — "
            "acquired by Columbia Financial (GlobeNewswire 2026-07-20).",
    "NUVL": "Nuvalent. Last bar 2026-07-14, pinned $123.9-123.96, delisted "
            "2026-07-16 — acquired by GSK (Investing.com 2026-06-11).",
    "OLPX": "Olaplex Holdings. Last bar 2026-07-06, pinned $2.05-2.07, "
            "delisted 2026-07-08 — acquired by Henkel (Benzinga 2026-03-26).",
    "P5N994": "Petrocorp Inc Escrow — an iShares R3000 NNQS placeholder, never "
              "a listed equity. Checked 2026-09-29: no Massive record, zero "
              "aggs ever, no cache frame.",
    "PRA": "ProAssurance. Last bar 2026-06-25, pinned at exactly $25.00, "
           "delisted 2026-06-29 — cash deal (GlobeNewswire 2025-06-15).",
    "RMAX": "RE/MAX Holdings. Last bar 2026-08-24 on ~6x volume, delisted "
            "2026-08-25 — acquired by Real Brokerage (Benzinga 2026-04-27).",
    "SEM": "Select Medical. Last bar 2026-06-30, pinned $16.50-16.53, "
           "delisted 2026-07-01 — take-private (GlobeNewswire 2026-03 merger "
           "probes).",
    "SILA": "Sila Realty Trust. Last bar 2026-06-30, pinned $30.29-30.36, "
            "delisted 2026-07-02 — buyout (Benzinga 2026-04-20).",
    "SKYT": "SkyWater Technology. Last bar 2026-07-30, delisted 2026-08-03 — "
            "acquired by IonQ (IONQ keeps its own series; Motley Fool "
            "2026-05-11).",
    "SMLR": "Semler Scientific. Last bar 2026-01-15, delisted 2026-01-20 — "
            "merged into Strive (GlobeNewswire 2025-12-09).",
    "SNBR": "Sleep Number. Last bar 2026-06-22, delisted 2026-06-23 after the "
            "June 12 Chapter 11 (Benzinga 2026-06-18). OTC SNBRQ is a "
            "bankrupt shell, not a rename.",
    "STEL": "Stellar Bancorp. Last bar 2026-06-30 on 15.9x volume, delisted "
            "2026-07-01 — merged into Prosperity Bancshares (Benzinga "
            "2026-01-28).",
    "TALK": "Talkspace. Last bar 2026-08-14, pinned $5.21-5.25, delisted "
            "2026-08-18 — acquired by UHS (Benzinga 2026-05-29).",
    "THR": "Thermon Group. Last bar 2026-05-29, delisted 2026-06-02 — "
           "combined into CECO Environmental (GlobeNewswire 2026-05-15).",
    "TMHC": "Taylor Morrison Home. Last bar 2026-07-23, pinned $71.85-72.48, "
            "delisted 2026-07-27 — acquired by Berkshire Hathaway (Benzinga "
            "2026-06-02).",
    "TWO": "Two Harbors Investment. Last bar 2026-08-24, pinned ~$12.0, "
           "delisted 2026-08-26 — acquired by CrossCountry (Benzinga "
           "2026-03-27). TWOD under the same CIK is senior notes: never map.",
    "WBS": "Webster Financial. Last bar 2026-08-19 on 18.8x volume, delisted "
           "2026-08-20 — acquired by Banco Santander (GlobeNewswire "
           "2026-05-18).",
    "WSR": "Whitestone REIT. Last bar 2026-07-13, pinned $18.96-19.00, "
           "delisted 2026-07-15 — acquired by Ares (GlobeNewswire 2026-04-09).",
    # --- 2026-09-29 Russell holdings refresh. Both are still listed in the
    # iShares R3000 file; verified against Massive live 2026-09-29: reference
    # NOT_FOUND, an inactive record with delisted_utc, no aggs after the last
    # bar, no same-CIK active successor.
    "THRD": "Third Harmonic Bio. Last bar 2025-07-30 (5.38, ~6x volume), "
            "pinned $5.38-5.45 for weeks, delisted_utc 2025-07-31 (CIK "
            "0001923840) — voluntary Nasdaq delisting under its Plan of "
            "Liquidation and Dissolution ($5.35/share first distribution; "
            "Form 25 filed 2025-07-31, SEC 8-K). Still an iShares IWV/IWC row "
            "at Price 0.00 on 2026-09-28.",
    "TBPH": "Theravance Biopharma. Last bar 2026-09-23, pinned $17.02-17.05 "
            "for five sessions, final two sessions 6.2M and 10.0M shares vs "
            "~0.4M before, delisted_utc 2026-09-24 (CIK 0001583107) — "
            "acquired by Zymeworks for $17.00 cash + a non-tradeable CVR, "
            "closed 2026-09-23 (GlobeNewswire 2026-09-23).",
    # --- 2026-10-07 missing-data audit (docs/sepa/missing_data_audit_2026_10_07.md).
    # Verified against Massive live 2026-10-07: reference shows an inactive
    # record with delisted_utc, the cached daily bars stop, and a by-CIK search
    # (active=true) returns NO successor. An acquirer that keeps its own series
    # is not a splice.
    "DBRG": "DigitalBridge Group. Inactive Massive record, delisted_utc "
            "2026-10-01 (CIK 0001679688, FIGI BBG00DM1FMT8); last cached bar "
            "2026-09-29, pinned $15.98-16.00; no active ticker under its CIK. "
            "Was #2 on the 🛡️ 🚀 growth order on a dead name.",
    "QRVO": "Qorvo. Inactive Massive record, delisted_utc 2026-10-06 (CIK "
            "0001604778, FIGI BBG007TJF1N7); last cached bar 2026-10-02 on 8.3M "
            "shares vs ~1.4M average; no active ticker under its CIK.",
    "GBTG": "Global Business Travel Group. Inactive Massive record, "
            "delisted_utc 2026-09-30 (CIK 0001820872); last cached bar "
            "2026-09-28, pinned $9.47-9.50, 3.9M shares vs ~1.7M average; no "
            "active ticker under its CIK. Watch-only on 2026-09-29; the "
            "delisting has since landed.",
    "PSKY": "Paramount Skydance Class B. Inactive Massive record, delisted_utc "
            "2026-10-06 (CIK 0002041610, FIGI BBG01VS5NK99); last cached bar "
            "2026-10-05 on 31.7M shares vs ~17.9M average; a by-CIK search "
            "(active=true) returns no successor under the same CIK. HIS CALL 12: "
            "WBD's bars stop the same day (merger close, a new holdco gets a NEW "
            "CIK); a by-name search 'Paramount' (active=true, 2026-10-07) lists "
            "only PZG (Paramount Gold Nevada) — any successor is not spliced.",
}


# ---------------------------------------------------------------------------
# First session of the CURRENT security under a reused / reorganised ticker
# ---------------------------------------------------------------------------
# {SYMBOL: (first_session_iso, evidence)}. Built 2026-09-29 from the Dual
# Momentum data audit (Ajay: WOLF +2,248.76%, SPCX +474.95% on his page).
#
# A provider serves ONE series per ticker, so when a ticker passes from one
# security to another (a Chapter 11 reorg that cancels the old equity, an ETF
# that closes and hands its symbol to an IPO) the new security's frame starts
# with the old one's bars. Every return that spans the handover is the ratio of
# two different companies' prices. That is not a rename: there is no history
# to splice, so the bars before `first_session` are dropped at read time
# (`prices._cut_foreign_head`).
#
# CURATED, NOT INFERRED — for the same reason as RENAMES: a wrong entry deletes
# real history from a chart real money is sized against. Every entry names the
# FIGI / list_date it was checked against. Never add an entry without them.
# A symbol here must NOT also be a RENAMES key or target (a test pins it).
FIRST_SESSION: dict[str, tuple[str, str]] = {
    "WOLF": ("2025-09-29",
             "Wolfspeed emerged from Chapter 11; the old equity was cancelled. "
             "Old FIGI BBG000BG14P4 (listed 1993-02-09) last bar 2025-09-26 "
             "close 1.21. New FIGI BBG01XLDHDP0, list_date 2025-09-29, "
             "Massive ticker event 2025-09-29; first bar open 18.00 / close "
             "22.10. No split record. That one day was 92% of the 12m log "
             "gain behind the page's +2,248.76%. Verified 2026-09-29."),
    "SPCX": ("2026-06-12",
             "Ticker reuse. SPCX was The SPAC and New Issue ETF (ETF, FIGI "
             "BBG00YJ8L8T5, ~$22) to 2026-04-06, then a 67-day hole, then "
             "SpaceX: list_date 2026-06-12 on XNAS, Massive ticker event "
             "2026-06-12, first bar open 150.00 / close 160.95 on 522M shares. "
             "Only ~75 SpaceX bars exist, so no real 6m / 12m return. "
             "Verified 2026-09-29."),
    "SOLS": ("2025-10-30",
             "Ticker reuse. Two sub-penny OTC SOLLENSYS CORP bars (2025-03/04), "
             "a 204-day hole, then Solstice Advanced Materials (Honeywell "
             "spin-off): list_date 2025-10-20, first regular bar 2025-10-30. "
             "The head produced a fake +48,739,900% day. Verified 2026-09-29."),
}


def first_session(symbol: str) -> Optional[str]:
    """First session (ISO date) of the security trading under ``symbol`` today,
    when a curated FIRST_SESSION entry exists; else None. PURE."""
    entry = FIRST_SESSION.get((symbol or "").strip().upper())
    return entry[0] if entry else None


def rename_effective(symbol: str) -> Optional[str]:
    """The ``effective`` date a NEW symbol started printing under a rename, or
    None. PURE.

    Looks the symbol up as a RENAMES *target* (via ``_FORMER``). With several
    former names the LATEST effective wins: that is the date the current
    symbol began printing. An OLD symbol (``SATS``) returns None — its own
    bars are all its own.
    """
    s = (symbol or "").strip().upper()
    effs = [RENAMES[old][1] for old in _FORMER.get(s, []) if old in RENAMES]
    return max(effs) if effs else None


def is_delisted(symbol: str) -> bool:
    """True when the symbol is a verified dead listing. PURE.

    Checks the symbol AS GIVEN (canonicalized), not resolve()d: a renamed
    symbol (IAC) is not delisted — it trades on as PPLI.
    """
    return (symbol or "").strip().upper() in DELISTED


# ---------------------------------------------------------------------------
# Per-provider spelling
# ---------------------------------------------------------------------------
# Our canonical spelling is the S&P / Wikipedia one: a dash before the share
# class (BRK-B). Providers disagree, and the disagreement is silent — a wrong
# spelling returns "no data", which is indistinguishable from "delisted".
def for_massive(symbol: str) -> str:
    """Massive spells class shares with a DOT: ``BRK-B`` → ``BRK.B``. PURE.

    Measured 2026-08-16 — Massive returns nothing at all for the dash form:

        BRK-B → None      BRK.B → 250 bars
        BF-B  → None      BF.B  → 250 bars
        MOG-A → None      MOG.A → 250 bars
        CWEN-A→ None      CWEN.A→ 177 bars

    Without this, every class share silently falls through to yfinance, mixing
    two providers' adjustment conventions inside one scan.
    """
    return _reclass(symbol, ".")


def for_yahoo(symbol: str) -> str:
    """Yahoo spells class shares with a DASH: ``BRK.B`` → ``BRK-B``. PURE."""
    return _reclass(symbol, "-")


# A class suffix is a single letter after the separator, at the very end. Only
# that shape is rewritten, so a symbol that legitimately contains a dot or dash
# elsewhere is left alone.
def _reclass(symbol: str, sep: str) -> str:
    if not symbol:
        return symbol
    s = symbol.strip().upper()
    for other in (".", "-"):
        if other == sep:
            continue
        head, found, tail = s.rpartition(other)
        if found and head and len(tail) == 1 and tail.isalpha():
            return f"{head}{sep}{tail}"
    return s


def yf_ticker(symbol: str):
    """``yfinance.Ticker`` for the symbol that trades TODAY, spelled Yahoo's way.

    Ajay 2026-08-16, from the deploy log right after the rename fix shipped::

        ERROR HTTP Error 404: No fundamentals data found for symbol: SQ

    The price path resolves renames; thirty-odd other call sites were still
    handing Yahoo the retired ticker, so a renamed company kept its chart and
    lost its profile, fundamentals, catalysts, earnings date and analyst
    ratings. Every one of those reads as "this company has no data", which is
    the same wrong story the delisted banner was telling.

    Use this instead of ``yf.Ticker`` anywhere the symbol came from a user, a
    watchlist or a scan. ``sepa.prices`` deliberately does NOT: its splice has
    to fetch the OLD symbol on purpose.

    Index symbols (``^VIX``) and anything not in ``RENAMES`` pass through
    untouched, so this is safe to apply blanket.
    """
    import yfinance as yf
    return yf.Ticker(for_yahoo(resolve(symbol)))


__all__ = ["RENAMES", "DELISTED", "FIRST_SESSION", "resolve", "former_names",
           "rename_of", "first_session", "rename_effective", "is_delisted",
           "for_massive", "for_yahoo", "yf_ticker"]
