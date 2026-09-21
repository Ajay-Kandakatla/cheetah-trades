"""Verbatim excerpts of Amaero Inc.'s S-1/A (accession 0001193125-26-395150,
filed 2026-09-18, primary document `project_alchemy_-_s-1a_2.htm`) plus four
synthetic covers, for `tests/test_ipo_upcoming_drill.py`.

The excerpts are slices of the BeautifulSoup-stripped text of the real
document, taken at the RAW offsets measured for the spec (before any
whitespace normalisation) — the `\xa0` runs and the mangled "TABL E OF
CONTENTS" are kept on purpose, because `chart_maps.ipo_upcoming._html_to_text`
normalises them and the extractor must be pinned against what it really sees.

Nothing here is a number the app uses. These are strings a prospectus printed.
The full 750 KB document is NEVER committed; it lives in the session
scratchpad only.

  COVER          the front cover: the offering sentence, the price sentence,
                 the bank list, the start of the table of contents
  OVERVIEW       "Overview We are a leading U.S.-based producer ..."
  SYMBOL_SECTION "Proposed trading symbol ... under the symbol "AMRO. "" and
                 the ASX ""3DA."" line right after it
  NET_LOSS       the summary Consolidated Statement of Operations: its own
                 units header "( in thousands, except share and per share
                 data)", its own period headers, and the four-column
                 "Net loss attributable to stockholders (1)" line
  KPI            the key-indicator block (a SECOND net-loss line, later)
  REVENUE        the MD&A results table: a DIFFERENT units header
                 "(in thousands)", a different period header, and the
                 "Total revenues from contracts with customers" line

`AMAERO_EXCERPTS` joins them with blank lines in document order.
"""
COVER = 'tock This is an initial public offering of shares of common stock of Amaero Inc. We are selling 7,456,500 shares of our common stock. Depositary interests, referred to as CHESS Depositary Interests (“CDIs”), each representing beneficial interests of 1/40th of a share of our common stock, are listed on the Australian Securities Exchange (“ASX”) under the symbol “3DA.” This prospectus does not constitute an offer to sell, or the solicitation of any offer to buy, any CDIs. On September 11, 2026, the last reported sales price of the CDIs was A$0.245 per CDI (equivalent to approximately $0.18 per CDI or $7.06 per share of common stock, based on the exchange rate of A$1.3872 per $1.00, the noon buying rate in effect on September 4, 2026 as quoted by the Federal Reserve Bank of New York in the United States). The initial public offering price of our common stock will be determined through negotiations between us and the underwriters and will be based on the last reported trading price of such CDI prior to the pricing of our Common Stock as well as prevailing market conditions and other factors described in “Underwriting” beginning on page 123 of this prospectus, subject to certain restrictions under the rules of the ASX (see “ Risk Factors—Our ability to raise additional capital may be significantly limited by the ASX Listing Rules that limit the amount of common stock that we are permitted to issue without stockholder approval. ”). Prior to this offering, there has been no public market for our common stock. We have applied to list our common stock on the Nasdaq Global Select Market (the “Nasdaq”) under the symbol “AMRO.” We are an “emerging growth company” and a “smaller reporting company” as defined under the federal securities laws and, as such, have elected to comply with certain reduced public company reporting requirements in this prospectus and may elect to do so in future filings. See “ Prospectus Summary—Implications of Being an Emerging Growth Company and a Smaller Reporting Company. ” Investing in our common stock involves a high degree of risk. See the section titled “Risk Factors” beginning on page 17 of this prospectus before making an investment decision regarding our common stock. \xa0 \xa0 \xa0 Per Share \xa0 \xa0 Total \xa0 Initial public offering price \xa0 $ \xa0 \xa0 \xa0 $ \xa0 \xa0 Underwriting discounts and commissions (1) \xa0 $ \xa0 \xa0 \xa0 $ \xa0 \xa0 Proceeds, before expenses, to Amaero Inc. \xa0 $ \xa0 \xa0 \xa0 $ \xa0 \xa0 \xa0 (1) See the section titled “Underwriting” for a description of the compensation payable to the underwriters. We have granted the underwriters an option to purchase up to an additional 1,118,475 shares of our common stock from us at the initial public offering price, less the underwriting discounts and commissions. Neither the Securities and Exchange Commission nor any state securities commission has approved or disapproved of these securities or passed upon the accuracy or adequacy of this prospectus. Any representation to the contrary is a criminal offense. The underwriters expect to deliver the shares against payment on , 2026. Joint Lead Bookrunning Managers \xa0 Stifel \xa0 Baird \xa0 Co-Manager Lake Street Prospectus dated , 2026 \xa0 Table of Contents \xa0 \xa0 \xa0 \xa0 Table of Contents \xa0 TABL E OF CONTENTS \xa0 \xa0 \xa0 Page MARKET, INDUSTRY AND OTHER DATA \xa0 iii PROSPECTUS SUMMARY \xa0 1 RISK FACTORS \xa0 17 CAUTIONARY NOTE REGARDING FORWARD-LOOKING STATEMENTS \xa0 42 USE OF PROCEEDS \xa0 44 DIVID'
OVERVIEW = 'where in this prospectus, before making an investment decision. Overview We are a leading U.S.-based producer of high-value refractory and titanium alloy spherical metal powders for additive manufacturing (“AM”) and advanced manufacturing, and a pioneer in Powder Metallurgy Hot Isostatic Pressing (“PM-HIP”) manufacturing of large near-net-shape components. With manufacturing and corporate headquarters in Tennessee, we occupy a strategically critical position at the intersection of U.S. national security priorities, AM technology, and the domestic reshoring of imperative U.S. supply chains. Our core technology platform centers on the Electrode Induction Melting Inert Gas Atomizer (“EIGA”), an advanced crucible-free gas atomization technology designed for the production of high-purity titani'
SYMBOL_SECTION = 's you should carefully consider before deciding to invest in our common stock. Proposed trading symbol We have applied to have our common stock listed on Nasdaq under the symbol “AMRO. ” Our CDIs are listed on the ASX under the symbol “3DA.” \xa0 The number of shares of common stock that will be outstanding immediately after this offering is based on 23,833,180 shares of our common stock outstanding '
NET_LOSS = ' this prospectus. Consolidated Statement of Operations ( in thousands, except share and per share data) \xa0 \xa0 \xa0 Year ended December 31, \xa0 \xa0 Six Months ended June 30, \xa0 \xa0 2025 \xa0 \xa0 2024 \xa0 \xa0 2026 \xa0 \xa0 2025 \xa0 Revenue \xa0 $ 6,305 \xa0 \xa0 $ 1,317 \xa0 \xa0 $ 7,397 \xa0 \xa0 $ 1,219 \xa0 Cost of revenue \xa0 \xa0 11,468 \xa0 \xa0 \xa0 4,160 \xa0 \xa0 \xa0 10,474 \xa0 \xa0 \xa0 4,496 \xa0 Gross loss \xa0 \xa0 (5,163 ) \xa0 \xa0 (2,843 ) \xa0 \xa0 (3,077 ) \xa0 \xa0 (3,277 ) Operating expenses: \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 Selling, general and administrative expenses \xa0 \xa0 13,400 \xa0 \xa0 \xa0 10,540 \xa0 \xa0 \xa0 9,963 \xa0 \xa0 \xa0 5,816 \xa0 Research and development expenses \xa0 \xa0 397 \xa0 \xa0 \xa0 541 \xa0 \xa0 \xa0 63 \xa0 \xa0 \xa0 8 \xa0 Loss on dispositions and impairment \xa0 \xa0 — \xa0 \xa0 \xa0 — \xa0 \xa0 \xa0 108 \xa0 \xa0 \xa0 — \xa0 Total operating expenses \xa0 \xa0 13,797 \xa0 \xa0 \xa0 11,081 \xa0 \xa0 \xa0 10,134 \xa0 \xa0 \xa0 5,824 \xa0 Loss from operations \xa0 \xa0 (18,960 ) \xa0 \xa0 (13,924 ) \xa0 \xa0 (13,211 ) \xa0 \xa0 (9,101 ) Other income, net \xa0 \xa0 151 \xa0 \xa0 \xa0 159 \xa0 \xa0 \xa0 86 \xa0 \xa0 \xa0 3 \xa0 Interest income \xa0 \xa0 715 \xa0 \xa0 \xa0 373 \xa0 \xa0 \xa0 389 \xa0 \xa0 \xa0 235 \xa0 Interest expense \xa0 \xa0 (454 ) \xa0 \xa0 (2 ) \xa0 \xa0 (697 ) \xa0 \xa0 (38 ) Total other income (expense), net \xa0 \xa0 412 \xa0 \xa0 \xa0 530 \xa0 \xa0 \xa0 (222 ) \xa0 \xa0 200 \xa0 Loss from continuing operations before \xa0\xa0\xa0income taxes \xa0 \xa0 (18,548 ) \xa0 \xa0 (13,394 ) \xa0 \xa0 (13,433 ) \xa0 \xa0 (8,901 ) Income tax benefit (expense) \xa0 \xa0 — \xa0 \xa0 \xa0 — \xa0 \xa0 \xa0 — \xa0 \xa0 \xa0 — \xa0 Loss from continuing operations \xa0 \xa0 (18,548 ) \xa0 \xa0 (13,394 ) \xa0 \xa0 (13,433 ) \xa0 \xa0 (8,901 ) Income from discontinued operations, net of tax \xa0 \xa0 170 \xa0 \xa0 \xa0 669 \xa0 \xa0 \xa0 — \xa0 \xa0 \xa0 170 \xa0 Net loss attributable to stockholders (1) \xa0 $ (18,378 ) \xa0 $ (12,725 ) \xa0 $ (13,433 ) \xa0 $ (8,731 ) Basic and diluted net loss per \xa0\xa0\xa0share - continuing operations \xa0 $ (0.96 ) \xa0 $ (0.98 ) \xa0 $ (0.56 ) \xa0 $ (0.53 ) Basic and diluted net income per \xa0\xa0\xa0share - discontinued operations \xa0 $ 0.01 \xa0 \xa0 $ 0.05 \xa0 \xa0 $ — \xa0 \xa0 $ 0.01 \xa0 Basic and diluted net loss per share \xa0 $ (0.95 ) \xa0 $ (0.93 ) \xa0 $ (0.56 ) \xa0 '
KPI = 'e Indicators \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 Backlog (1) \xa0 $ 6,873 \xa0 \xa0 $ 439 \xa0 \xa0 $ 10,013 \xa0 \xa0 $ 3,175 \xa0 Net loss attributable to Amaero Inc. stockholders \xa0 $ (18,378 ) \xa0 $ (12,725 ) \xa0 $ (13,433 ) \xa0 $ (8,731 ) Net cash used in operating activities \xa0 $ (18,361 ) \xa0 $ (11,342 ) \xa0 $ (12,903 ) \xa0 $ (6,985 ) Non-GAAP Financial Measures \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 Adjusted EBITDA (2) \xa0 $ (15,160 ) \xa0 $ (11,034 ) \xa0 $ (8,512 ) \xa0 $ (7,480 ) \xa0 (1) See “—Backlog” for more information (2) Adjusted EBITDA is a non-GAAP fina'
REVENUE = 'ing operations for the periods presented (in thousands). The discussion that follows compares our results of continuing operations for the year ended December 31, 2025 to the year ended December 31, 2024. Income from discontinued operations is discussed at the end of this section, and additional information regarding our discontinued operations is included in Note 21 — Discontinued Operations in our consolidated financial statements. \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 Change \xa0 Year ended December 31, \xa0 2025 \xa0 \xa0 2024 \xa0 \xa0 $ \xa0 \xa0 % \xa0 Revenue \xa0 $ 6,305 \xa0 \xa0 $ 1,317 \xa0 \xa0 $ 4,988 \xa0 \xa0 \xa0 379 % Cost of revenue \xa0 \xa0 11,468 \xa0 \xa0 \xa0 4,160 \xa0 \xa0 \xa0 7,308 \xa0 \xa0 \xa0 176 % Gross loss \xa0 \xa0 (5,163 ) \xa0 \xa0 (2,843 ) \xa0 \xa0 (2,320 ) \xa0 \xa0 82 % Operating expenses: \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 Selling, general and administrative expenses \xa0 \xa0 13,400 \xa0 \xa0 \xa0 10,540 \xa0 \xa0 \xa0 2,860 \xa0 \xa0 \xa0 27 % Research and development expenses \xa0 \xa0 397 \xa0 \xa0 \xa0 541 \xa0 \xa0 \xa0 (144 ) \xa0 \xa0 -27 % Total operating expenses \xa0 \xa0 13,797 \xa0 \xa0 \xa0 11,081 \xa0 \xa0 \xa0 2,716 \xa0 \xa0 \xa0 25 % Loss from operations \xa0 \xa0 (18,960 ) \xa0 \xa0 (13,924 ) \xa0 \xa0 (5,036 ) \xa0 \xa0 36 % Other income, net \xa0 \xa0 151 \xa0 \xa0 \xa0 159 \xa0 \xa0 \xa0 (8 ) \xa0 \xa0 -5 % Interest income \xa0 \xa0 715 \xa0 \xa0 \xa0 373 \xa0 \xa0 \xa0 342 \xa0 \xa0 \xa0 92 % Interest expense \xa0 \xa0 (454 ) \xa0 \xa0 (2 ) \xa0 \xa0 (452 ) \xa0 N/M \xa0 Total other income (expense), net \xa0 \xa0 412 \xa0 \xa0 \xa0 530 \xa0 \xa0 \xa0 (118 ) \xa0 \xa0 -22 % Loss from continuing operations before income taxes \xa0 \xa0 (18,548 ) \xa0 \xa0 (13,394 ) \xa0 \xa0 (5,154 ) \xa0 \xa0 38 % Income tax benefit (expense) \xa0 — \xa0 \xa0 — \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 Loss from continuing operations \xa0 \xa0 (18,548 ) \xa0 \xa0 (13,394 ) \xa0 \xa0 (5,154 ) \xa0 \xa0 38 % Income from discontinued operations, net of tax \xa0 \xa0 170 \xa0 \xa0 \xa0 669 \xa0 \xa0 \xa0 (499 ) \xa0 \xa0 -75 % Net loss attributable to Amaero Inc. stockholders \xa0 $ (18,378 ) \xa0 $ (12,725 ) \xa0 $ (5,653 ) \xa0 \xa0 44 % \xa0 N/M = not meaningful Revenue Revenue increased $5.0 million from $1.3 million in 2024 to $6.3 million in 2025. This growth reflects the progressive ramp of our Tennessee manufacturing operations as customers completed qualification programs and began drawing on contracted volumes. \xa0 \xa0 \xa0 \xa0 Change \xa0 December 31, \xa0 2025 \xa0 \xa0 2024 \xa0 \xa0 $ \xa0 \xa0 % \xa0 Major Product line \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 \xa0 Metal powders \xa0 $ 5,277 \xa0 \xa0 $ 678 \xa0 \xa0 $ 4,599 \xa0 \xa0 \xa0 678 % PM-HIP components \xa0 \xa0 1,028 \xa0 \xa0 \xa0 639 \xa0 \xa0 \xa0 389 \xa0 \xa0 \xa0 61 % Total revenues from contracts with customers \xa0 $ 6,305 \xa0 \xa0 $ 1,317 \xa0 \xa0 $ 4,988 \xa0 \xa0 \xa0 379 % \xa0 Metal powders revenue increased $4.6 million from $0.7 million in 2024 to $5.3 million in 2025. The increase reflects the early-stage ramp of our atomization capacity following the commi'

AMAERO_EXCERPTS = "\n\n".join(
    (COVER, OVERVIEW, SYMBOL_SECTION, NET_LOSS, KPI, REVENUE))


# ── synthetic covers ────────────────────────────────────────────────────────
# A cover that DOES print a price range (Amaero's does not) and three banks
# whose canonical names collapse the "Roth Capital"/"Roth" alias pair.
RANGE_COVER = (
    "Preliminary Prospectus Dated September 18, 2026 5,000,000 shares "
    "Synthetic Range Co. Common Stock We are offering 5,000,000 shares of "
    "our common stock. No public market currently exists for our common "
    "stock. We currently estimate that the initial public offering price "
    "will be between $18.00 and $20.00 per share. Investing in our common "
    "stock involves risks. Joint Book-Running Managers Goldman Sachs & Co. "
    "LLC J.P. Morgan Co-Manager Roth Capital Partners Prospectus dated , "
    "2026"
)

# ONE table that carries BOTH quotes under ONE units header and ONE period
# header, with "Ended" capitalised — the "present" case for
# `_table_header_lines`.
HEADER_TABLE = (
    "Selected financial data (in millions, except per share data) Fiscal "
    "Years Ended January 31, 2026 and 2025 Net revenues $ 1,234 $ 987 Net "
    "loss $ (156 ) $ (278 ) See the notes to our financial statements."
)

# A cover whose running text says "underwriters" in LOWERCASE well before the
# bank list. A case-insensitive segment anchor opens here and never reaches
# Stifel or Baird.
LOWER_UNDERWRITERS_COVER = (
    "Synthetic Lowercase Co. Common Stock We are selling 2,000,000 shares "
    "of our common stock. The initial public offering price will be "
    "determined through negotiations between us and the underwriters and "
    "will be based on the last reported price of our ordinary shares. "
    + ("Neither the Securities and Exchange Commission nor any state "
       "securities commission has approved or disapproved of these "
       "securities or passed upon the adequacy or accuracy of this "
       "prospectus. ") * 6
    + "Joint Bookrunning Managers Stifel Baird Prospectus dated , 2026"
)

# Prose with none of the anchors: every scalar the extractor reads must come
# back None, and `underwriters` must come back [] (the one list).
NOTHING = (
    "This document describes the weather in three cities and the history of "
    "the cooperative movement. There is no offering here, no exchange "
    "listing, no bank, no table and no financial statement of any kind. "
    "Nothing was filed and nothing is expected."
)
