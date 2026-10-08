"""Massive v1 fundamentals — the ONE reader of filed financial statements.

WHY THIS FILE EXISTS (2026-09-30)
─────────────────────────────────
Massive's vX financials endpoint answers `Deprecation: true` and
`Sunset: 2026-10-09`, and it was already in 410 brownouts the day this was
written (MU and CRWD 410'd on the probe; NVDA answered). Its `Link` header names
the successor: the v1 fundamentals family,

    /stocks/financials/v1/income-statements
    /stocks/financials/v1/balance-sheets
    /stocks/financials/v1/cash-flow-statements

Four live modules read vX — `canslim` (C/A EPS), `longterm` (the Fundamentals
tab), `board_metrics` (dilution) and, through board_metrics' payload,
`capital_returns` (ROCE/ROIC). They all read the SAME vX report shape, so this
module fetches v1 and hands back reports in THAT shape:

    {"fiscal_year": 2027, "fiscal_period": "Q2" | "FY", "timeframe": ...,
     "end_date": "2026-07-26", "filing_date": "2026-08-26" | None,
     "financials": {"income_statement": {"revenues": {"value": 1.0}}, ...}}

so every downstream formula, alignment and guard runs unchanged. The field map
below is the migration's record — every vX key a live module reads, and the v1
key it now comes from. A key that is not in the map is never produced, so a
consumer reading an unmapped key gets None (unknown), never a zero.

SEVEN SEMANTIC CHANGES — READ BEFORE TRUSTING AN OLD NUMBER
───────────────────────────────────────────────────────────
1. v1 ZERO-FILLS ABSENT LINES. A line the filing does not have comes back as
   0.0, never null (and now and then the key is missing outright — ARR's FY2020
   annual row has no `revenue`). Measured 2026-09-30: ARR
   and DX (mortgage REITs) report `income_taxes: 0.0` where vX had no tax line,
   and CRWD/ARR/DX report `inventories: 0.0` where vX had no inventory line. A
   zero there is indistinguishable from "not filed", so an exact 0.0 on a
   mapped line is read as ABSENT (None) — the house rule, a blank is never a
   zero. Cost, accepted: a genuine $0.00 EPS quarter also reads as unknown.

2. v1 HAS NO "DERIVED" MARKER. vX left `filing_date: None` on a derived Q4
   (annual minus the three 10-Q quarters) and `board_metrics` keys its entire
   share-count guard on that. v1 stamps Q4 with the 10-K's date — but no 10-Q
   exists for a fourth quarter, so every quarterly Q4 is still derived, and the
   share count still goes wrong at the edges (v1 NVDA FY2024 Q4 reads
   47,336,000,000 diluted shares against ~24.9 B either side). So a QUARTERLY
   Q4 is emitted with `filing_date: None` exactly as vX did, and the v1 stamp
   rides beside it as `v1_filing_date`. Annual rows keep their date.

3. v1 FILING DATES ARE RESTATED. `filing_date` is "the most recent SEC filing
   that included this period's data", not the original filing: NVDA FY2026 Q2
   reads 2026-08-26 on v1 (the next year's 10-Q comparative) against 2025-08-27
   on vX. The LATEST period's date is still its own filing; older periods move
   forward. Nothing here orders or gates on an old period's filing date.

4. v1 VALUES ARE RESTATED TOO — split-adjusted and rounded. NVDA FY2025 Q1
   diluted EPS is 0.60 on v1 against 5.98 on vX (pre-10:1-split basis), and
   restated comparatives round to the filing's units (SM FY2025 Q2 revenue
   793,000,000 against vX 792,943,000). vX mixed split bases inside one series;
   v1 does not. v1 carries only LISTED names — a delisted ticker answers an
   empty list, where vX still had its filings.

5. v1's QUARTERLY Q4 EPS rides the broken Q4 share count (NFLX FY2024 Q4 0.11
   against ~0.43). `derive_q4_eps` puts back vX's annual − (Q1+Q2+Q3).

6. STRAY COMPARATIVE ROWS + TICKER ≠ COMPANY. Balance sheets carry prior-year
   comparatives under a wrong label (PEP `2025-12-27 FY2025 Q1`), so the
   INCOME statement is the spine and the others attach to its periods — see
   `_attach`. `tickers=` can span two companies (MU) or come back short for a
   renamed ticker (SGI) — see `fetch_statement`.

7. THE REVENUE LINE FOLLOWS v1's STATEMENT TEMPLATE (2026-10-08). v1 serves a
   bank's `revenue` GROSS — interest income plus noninterest income — with
   total interest expense as `cost_of_revenue`: BAC Q2-2026 reads 49,393 M
   against the 10-Q's "Total revenue, net of interest expense" 31,558 M
   (49,393 − 17,835). The template is told apart by KEY PRESENCE, never by a
   zero: a bank/broker/lender row carries neither `interest_expense` nor
   `research_development` (MEASURED 2026-10-07: 380 of 1,409 rows, 38 of 141
   names, constant per name), an insurer row lacks only `research_development`,
   and every other row carries both zero-filled. Financial template →
   revenue − cost_of_revenue + other_income_expense (C Q2-2026: 24,262 + 504 =
   24,766 M = the 10-Q); every other template → v1 `revenue` as before. Six
   names the verifier reproduced at % AND both levels take a CIK-keyed pick
   (`REVENUE_LINE_PICKS`), 34 more keep their value but carry a hold note
   (`REVENUE_LINE_HOLD`, shown with * on 🛡️). A financial-template quarter
   with no cost line is a HOLE (`LINE_UNDETERMINED`) — never gross revenue.
   See `revenue_line` and docs/sepa/revenue_lines_2026_10_08.md.

FAIL LOUDLY
───────────
`fetch_reports` returns [] ONLY when the provider answered 200 with no filings
(an ETF, a trust, a delisted name). Every other failure — 410, 401/403, a 429 or
5xx that survives its retries, a transport error, a malformed body — raises
`FinancialsUnavailable` with a short reason code, so a caller can tell "this
company files nothing" from "the provider did not answer" and say which on the
page. The key rides in the Authorization header, never the URL, so no
exception string can carry it (this repo has leaked the Massive key five times
through URL-bearing exception text).
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Iterable, Optional

log = logging.getLogger("sepa.massive_fundamentals")

BASE = "https://api.massive.com/stocks/financials/v1/"

INCOME = "income_statement"
BALANCE = "balance_sheet"
CASH_FLOW = "cash_flow_statement"
ALL_STATEMENTS = (INCOME, BALANCE, CASH_FLOW)

ENDPOINTS = {
    INCOME: "income-statements",
    BALANCE: "balance-sheets",
    CASH_FLOW: "cash-flow-statements",
}

# vX key -> v1 key, per statement. Every vX key a LIVE module reads, verified
# against a live v1 row 2026-09-30. Semantic notes where the v1 line is not a
# like-for-like rename:
#   net_income_loss      -> consolidated_net_income_loss (incl. minority share,
#                           same as vX's NetIncomeLoss)
#   long_term_debt       -> long_term_debt_and_capital_lease_obligations (v1
#                           has no bare LTD line; this one includes finance
#                           leases — `longterm` stores it for history only)
#   diluted_average_shares -> diluted_shares_outstanding (v1 names it
#                           "outstanding" but documents it as the WEIGHTED
#                           AVERAGE, which is what vX carried)
FIELD_MAP = {
    INCOME: {
        # the STANDARD-template line; `revenue_line` chooses per row template
        # since 2026-10-08 (semantic change 7)
        "revenues": "revenue",
        "diluted_earnings_per_share": "diluted_earnings_per_share",
        "basic_earnings_per_share": "basic_earnings_per_share",
        "net_income_loss": "consolidated_net_income_loss",
        "operating_income_loss": "operating_income",
        "gross_profit": "gross_profit",
        "income_loss_from_continuing_operations_before_tax": "income_before_income_taxes",
        "income_tax_expense_benefit": "income_taxes",
        "diluted_average_shares": "diluted_shares_outstanding",
        "basic_average_shares": "basic_shares_outstanding",
    },
    BALANCE: {
        "inventory": "inventories",
        "assets": "total_assets",
        "liabilities": "total_liabilities",
        "equity": "total_equity",
        "equity_attributable_to_parent": "total_equity_attributable_to_parent",
        "current_assets": "total_current_assets",
        "current_liabilities": "total_current_liabilities",
        "long_term_debt": "long_term_debt_and_capital_lease_obligations",
    },
    CASH_FLOW: {
        "net_cash_flow_from_operating_activities": "net_cash_from_operating_activities",
        "net_cash_flow": "change_in_cash_and_equivalents",
    },
}

# The one vX line v1 does not carry under any name: net income attributable to
# the PARENT. v1 carries the consolidated line and the minority ADJUSTMENT
# (`noncontrolling_interest`, signed so the two ADD to the parent's share):
# BX 2026-06-30 2,356,066,000 + (−1,126,877,000) = 1,229,189,000; CEG
# 508 M + 5 M = 513 M. An earlier build used common + preferred dividends,
# which agrees on BX and GOOGL but NOT on ~5% of names (critic 2026-09-30,
# 10 of 200: TDG 386 vs 445, OXY 2,787 vs 2,977, TSN 88 vs 47 — v1 files
# participating-security and other items under "preferred dividends").
# Kept as a named sum so the provenance is one grep away. The first addend
# must be present; an absent adjustment (0.0) means no minority interest.
DERIVED = {
    INCOME: {
        "net_income_loss_attributable_to_parent": (
            "consolidated_net_income_loss",
            "noncontrolling_interest",
        ),
    },
}

# ─────────────────────────────── semantic change 7: the revenue line (2026-10-08)
TEMPLATE_FINANCIAL, TEMPLATE_INSURANCE, TEMPLATE_STANDARD = "financial", "insurance", "standard"
FIN_TEMPLATE_ABSENT_KEYS = ("interest_expense", "research_development")   # BOTH missing = financial template.
#   MEASURED 2026-10-07: 380 of 1,409 rows (38 of 141 names) — missing, never zero-filled; standard rows carry both as 0.0.
INS_TEMPLATE_ABSENT_KEY = "research_development"                          # missing alone = insurance template (60 rows, 6 names)

LINE_REVENUE = "revenue"                       # v1 `revenue` as served
LINE_NET_OF_INTEREST = "net_of_interest"       # revenue − cost_of_revenue + other_income_expense (financial template)
LINE_PLUS_OTHER = "revenue_plus_other"         # revenue + other_income_expense (pick)
LINE_PLUS_INTEREST = "revenue_plus_interest"   # revenue + interest_income (pick)
LINE_UNDETERMINED = "undetermined"             # financial-template quarter with no cost line → hole
LINE_CODES = (LINE_REVENUE, LINE_NET_OF_INTEREST, LINE_PLUS_OTHER, LINE_PLUS_INTEREST, LINE_UNDETERMINED)
LINE_WORDS = {
    LINE_REVENUE: "revenue",
    LINE_NET_OF_INTEREST: "total revenue net of interest expense",
    LINE_PLUS_OTHER: "revenue + other income",
    LINE_PLUS_INTEREST: "revenue + interest income",
    LINE_UNDETERMINED: "no revenue line this quarter (the provider's bank-template row has no interest-expense line to net)",
}
HOLD_UNVERIFIED, HOLD_HIS_CALL = "unverified", "his_call"

NOTE_NO_NII = ("the provider has no net-interest-income line, so its revenue is a fee sub-line, "
               "not the 10-Q's total net revenue")
NOTE_DROPS_INCOME = ("the provider's revenue leaves out income the 10-Q's total includes "
                     "(investment, trading, interest or retirement-services income)")
NOTE_LEASE_DEPRECIATION = ("the 10-Q's total net revenue is after operating-lease depreciation, "
                           "which the provider does not carry")
NOTE_FOREIGN_FILER = ("a foreign filer (IFRS, 6-K/20-F): the SEC has no quarterly XBRL to check "
                      "the provider's line against")
NOTE_NO_REVENUE_LINE = "the 10-Q prints no revenue line (interest income and net interest income instead)"
NOTE_NO_MATCHING_LINE = "the provider's revenue matches no line on the 10-Q's income statement"
NOTE_PICK_UNCONFIRMED = ("the 10-Q's total adds interest income to revenue; a revenue + interest-income "
                         "pick is measured but not yet cross-checked")
NOTE_SUBLINE_CALL = ("the provider carries a sub-line of the 10-Q (sales before other income, or one segment); "
                     "which line ranks is pending a decision")
NOTE_PICK_SHAPE_CHANGED = "the per-name revenue pick no longer matches the provider's row shape — re-check it"

# CIK (v1 `cik`, 10-digit string) -> (ticker, template it was measured on, line). Reproduced at % AND both
# quarter levels by the verifier (critic_table.json) and the R-file table (ta_match_table.json), Q2-2026.
# HIS CALL home: a pick is promoted / retired HERE (docs/sepa/revenue_lines_2026_10_08.md).
REVENUE_LINE_PICKS = {
    "0001805284": ("RKT",  TEMPLATE_FINANCIAL, LINE_REVENUE),        # 'Total revenue, net' 2,784 / 1,451 M = v1 revenue
    "0001397911": ("LPLA", TEMPLATE_FINANCIAL, LINE_PLUS_OTHER),     # 5,038.2 + 148.4 = 5,186.6 M 'Total net revenues'
    "0000064803": ("CVS",  TEMPLATE_STANDARD,  LINE_PLUS_INTEREST),  # 105,455 + 641 = 106,096 M 'Total revenues'
    "0000079282": ("BRO",  TEMPLATE_STANDARD,  LINE_PLUS_INTEREST),  # 1,654 + 22 = 1,676 M 'Total revenues'
    "0000726728": ("O",    TEMPLATE_STANDARD,  LINE_PLUS_INTEREST),  # 1,426.5 + 120.5 = 1,547.0 vs 1,547.7 M 'Total revenue'
    "0001645590": ("HPE",  TEMPLATE_STANDARD,  LINE_PLUS_INTEREST),  # 12,021 + 192 = 12,213 M 'Total net revenue'
}
# CIK -> (ticker, kind, note). The VALUE is unchanged (template rule / plain); 🛡️ shows it with * and the note.
# HIS CALL home: an entry leaves the ledger only on his decision or a cross-check.
REVENUE_LINE_HOLD = {
    "0001818874": ("SOFI", HOLD_UNVERIFIED, NOTE_NO_NII),
    "0001381197": ("IBKR", HOLD_UNVERIFIED, NOTE_NO_NII),
    "0001393818": ("BX",   HOLD_UNVERIFIED, NOTE_DROPS_INCOME),
    "0001858681": ("APO",  HOLD_UNVERIFIED, NOTE_DROPS_INCOME),
    "0001592386": ("VIRT", HOLD_UNVERIFIED, NOTE_DROPS_INCOME),
    "0001820953": ("AFRM", HOLD_UNVERIFIED, NOTE_DROPS_INCOME),
    "0000766704": ("WELL", HOLD_UNVERIFIED, NOTE_DROPS_INCOME),
    "0000040729": ("ALLY", HOLD_UNVERIFIED, NOTE_LEASE_DEPRECIATION),
    "0001691493": ("NU",   HOLD_UNVERIFIED, NOTE_FOREIGN_FILER),
    "0001043219": ("NLY",  HOLD_UNVERIFIED, NOTE_NO_REVENUE_LINE),
    "0000821189": ("EOG",  HOLD_UNVERIFIED, NOTE_NO_MATCHING_LINE),
    "0000895126": ("EXE",  HOLD_UNVERIFIED, NOTE_NO_MATCHING_LINE),
    "0001792580": ("OVV",  HOLD_UNVERIFIED, NOTE_NO_MATCHING_LINE),
    "0001623925": ("AM",   HOLD_UNVERIFIED, NOTE_NO_MATCHING_LINE),
    "0001311370": ("LAZ",  HOLD_UNVERIFIED, NOTE_NO_MATCHING_LINE),
    "0000895417": ("ELS",  HOLD_UNVERIFIED, NOTE_NO_MATCHING_LINE),
    "0000935703": ("DLTR", HOLD_UNVERIFIED, NOTE_NO_MATCHING_LINE),
    "0001801368": ("MP",   HOLD_UNVERIFIED, NOTE_NO_MATCHING_LINE),
    "0001020214": ("CERS", HOLD_UNVERIFIED, NOTE_NO_MATCHING_LINE),
    "0000765880": ("DOC",  HOLD_UNVERIFIED, NOTE_PICK_UNCONFIRMED),
    "0000751364": ("NNN",  HOLD_UNVERIFIED, NOTE_PICK_UNCONFIRMED),
    "0001571283": ("REXR", HOLD_UNVERIFIED, NOTE_PICK_UNCONFIRMED),
    "0001465128": ("STWD", HOLD_UNVERIFIED, NOTE_PICK_UNCONFIRMED),
    "0000912593": ("SUI",  HOLD_UNVERIFIED, NOTE_PICK_UNCONFIRMED),
    "0000740260": ("VTR",  HOLD_UNVERIFIED, NOTE_PICK_UNCONFIRMED),
    "0001567094": ("CNH",  HOLD_UNVERIFIED, NOTE_PICK_UNCONFIRMED),
    "0000093410": ("CVX",  HOLD_HIS_CALL,   NOTE_SUBLINE_CALL),
    "0001090012": ("DVN",  HOLD_HIS_CALL,   NOTE_SUBLINE_CALL),
    "0000315852": ("RRC",  HOLD_HIS_CALL,   NOTE_SUBLINE_CALL),
    "0001520006": ("MTDR", HOLD_HIS_CALL,   NOTE_SUBLINE_CALL),
    "0001841666": ("APA",  HOLD_HIS_CALL,   NOTE_SUBLINE_CALL),
    "0000091440": ("SNA",  HOLD_HIS_CALL,   NOTE_SUBLINE_CALL),
    "0000927066": ("DVA",  HOLD_HIS_CALL,   NOTE_SUBLINE_CALL),
    "0001045450": ("EPR",  HOLD_HIS_CALL,   NOTE_SUBLINE_CALL),
}

# Retries: a 429 or 5xx is the provider saying "not now"; a 410 is it saying
# "never" and is raised at once — v1 going the way of vX must be SEEN the first
# time, not retried into a slow scan.
MAX_ATTEMPTS = 3
RETRY_STATUSES = (429, 500, 502, 503, 504)
BACKOFF_SEC = 1.0          # 1 s, then 2 s — doubled per attempt
MAX_RETRY_AFTER_SEC = 10.0  # a Retry-After is honoured up to this, never longer

_sleep = time.sleep          # swapped out by the tests


class FinancialsUnavailable(RuntimeError):
    """The provider did not answer — NOT "this company files nothing".

    `reason` is a short stable code a caller can put on a page:
    endpoint_gone (410), not_authorized (401/403), rate_limited (429 after
    retries), server_error (5xx after retries), http_<code>, transport_error,
    bad_payload, no_key.
    """

    def __init__(self, reason: str, *, symbol: str = "", status: Optional[int] = None,
                 endpoint: str = ""):
        self.reason = reason
        self.symbol = symbol
        self.status = status
        self.endpoint = endpoint
        tail = f" HTTP {status}" if status is not None else ""
        super().__init__(f"{symbol} {endpoint}: {reason}{tail}".strip())


def _value(v) -> Optional[float]:
    """A v1 number as a finite float, or None. An exact 0.0 is ABSENT — see
    semantic change 1 in the module docstring."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return None if f == 0.0 else f


def _cell(v: Optional[float]) -> Optional[dict]:
    return None if v is None else {"value": v}


def row_template(row: dict) -> str:
    """The v1 statement template of ONE income row, by KEY PRESENCE only —
    a zero-filled key is present (standard), a missing one is not. PURE."""
    row = row if isinstance(row, dict) else {}
    if all(k not in row for k in FIN_TEMPLATE_ABSENT_KEYS):
        return TEMPLATE_FINANCIAL
    if INS_TEMPLATE_ABSENT_KEY not in row:
        return TEMPLATE_INSURANCE
    return TEMPLATE_STANDARD


def revenue_line(row: dict, *, cik: Optional[str] = None) -> tuple:
    """(value, line_code, note) for ONE v1 income row. PURE.

    The line follows the row's template (semantic change 7): financial →
    revenue − cost_of_revenue + other_income_expense; insurance / standard →
    v1 `revenue`. A CIK in `REVENUE_LINE_PICKS` takes its pick ONLY on the
    template it was measured on — on any other shape the pick is ignored and
    the note says so (shown *, never silent). A financial-template quarter with
    no revenue or no cost line is `LINE_UNDETERMINED` with value None — NEVER
    gross revenue. `note` is the hold ledger's note when the CIK is on it.
    """
    row = row if isinstance(row, dict) else {}
    cik = cik or row.get("cik")
    cik = str(cik) if cik else None
    tmpl = row_template(row)
    rev = _value(row.get("revenue"))
    note = None
    pick = REVENUE_LINE_PICKS.get(cik) if cik else None
    if pick is not None and pick[1] != tmpl:
        note, pick = NOTE_PICK_SHAPE_CHANGED, None
    if pick is not None:
        line = pick[2]
    else:
        line = LINE_NET_OF_INTEREST if tmpl == TEMPLATE_FINANCIAL else LINE_REVENUE
    value: Optional[float]
    if line == LINE_REVENUE:
        value = rev
    elif line == LINE_NET_OF_INTEREST:
        cor = _value(row.get("cost_of_revenue"))
        if rev is None or cor is None:
            value, line = None, LINE_UNDETERMINED
        else:
            value = _value(rev - cor + (_value(row.get("other_income_expense")) or 0.0))
    elif line == LINE_PLUS_OTHER:
        value = None if rev is None else _value(rev + (_value(row.get("other_income_expense")) or 0.0))
    elif line == LINE_PLUS_INTEREST:
        value = None if rev is None else _value(rev + (_value(row.get("interest_income")) or 0.0))
    else:                                                   # pragma: no cover — LINE_CODES is closed
        value, line = None, LINE_UNDETERMINED
    if note is None and cik in REVENUE_LINE_HOLD:
        note = REVENUE_LINE_HOLD[cik][2]
    return value, line, note


def _get(url: str, params: dict, key: str, *, symbol: str, endpoint: str,
         timeout: float) -> dict:
    """One GET with the retry policy. Returns the decoded JSON body."""
    import requests
    headers = {"Authorization": f"Bearer {key}"}
    last_status: Optional[int] = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
        except Exception as exc:                               # noqa: BLE001
            # Type name only — never the exception text (see module docstring).
            log.debug("massive_fundamentals: %s %s transport %s",
                      symbol, endpoint, type(exc).__name__)
            last_status = None
            if attempt + 1 < MAX_ATTEMPTS:
                _sleep(BACKOFF_SEC * (2 ** attempt))
                continue
            raise FinancialsUnavailable("transport_error", symbol=symbol,
                                        endpoint=endpoint) from None
        status = r.status_code
        if status == 200:
            try:
                body = r.json()
            except Exception:                                  # noqa: BLE001
                raise FinancialsUnavailable("bad_payload", symbol=symbol,
                                            status=status, endpoint=endpoint) from None
            if not isinstance(body, dict) or not isinstance(body.get("results", []), list):
                raise FinancialsUnavailable("bad_payload", symbol=symbol,
                                            status=status, endpoint=endpoint)
            return body
        if status == 410:
            log.warning("massive_fundamentals: %s answered 410 GONE — the v1 "
                        "fundamentals endpoint is being retired too", endpoint)
            raise FinancialsUnavailable("endpoint_gone", symbol=symbol,
                                        status=status, endpoint=endpoint)
        if status in (401, 403):
            raise FinancialsUnavailable("not_authorized", symbol=symbol,
                                        status=status, endpoint=endpoint)
        if status in RETRY_STATUSES and attempt + 1 < MAX_ATTEMPTS:
            last_status = status
            wait = BACKOFF_SEC * (2 ** attempt)
            try:
                ra = float((r.headers or {}).get("Retry-After"))
                if ra >= 0:
                    wait = min(ra, MAX_RETRY_AFTER_SEC)
            except (TypeError, ValueError):
                pass
            _sleep(wait)
            continue
        reason = ("rate_limited" if status == 429
                  else "server_error" if 500 <= status < 600
                  else f"http_{status}")
        raise FinancialsUnavailable(reason, symbol=symbol, status=status,
                                    endpoint=endpoint)
    # Unreachable: every branch above returns, continues or raises.
    raise FinancialsUnavailable("transport_error", symbol=symbol,
                                status=last_status, endpoint=endpoint)


def _newest_cik(rows: list) -> Optional[str]:
    """The CIK that filed the NEWEST period — the company the ticker means
    today. None when no row names one."""
    named = [r for r in rows if r.get("cik")]
    if not named:
        return None
    return max(named, key=lambda r: str(r.get("period_end") or ""))["cik"]


def _label(row: dict, timeframe: str) -> Optional[tuple]:
    """The fiscal label of a v1 row: (FY, quarter) — or (FY, "FY") annual."""
    try:
        fy = int(row.get("fiscal_year"))
    except (TypeError, ValueError):
        return None
    if timeframe == "annual":
        return (fy, "FY")
    try:
        fq = int(row.get("fiscal_quarter"))
    except (TypeError, ValueError):
        return None
    return (fy, fq) if 1 <= fq <= 4 else None


def _day(v) -> Optional[date]:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _newer_filing(a: dict, b: Optional[dict]) -> bool:
    return b is None or str(a.get("filing_date") or "") > str(b.get("filing_date") or "")


def fetch_statement(symbol: str, statement: str, *, timeframe: str, limit: int,
                    key: str, timeout: float = 12.0, cik: Optional[str] = None,
                    since: Optional[str] = None, want: Optional[int] = None) -> tuple:
    """`(rows, cik)` — raw v1 rows for ONE company, newest period first.

    ONE COMPANY, FULL HISTORY. `tickers=X` matches every CIK that has carried
    X, so a recycled ticker interleaves two companies — measured 2026-09-30:
    `tickers=MU` answers 14 annual rows of which 3 are CIK 798287 (a ~$500 M
    revenue company), not Micron. Dropping them left Micron 9 years where it
    has 12. A RENAMED ticker is the mirror case: `tickers=SGI` answers one
    annual income row while its CIK holds twelve. So once the company is known
    (the CIK that filed the NEWEST period) the statement is re-asked by `cik=`
    whenever the ticker answer spans several companies or came back short of
    `limit`, and every later statement is asked by that CIK directly.

    `since` (an ISO date) bounds the answer to `period_end >= since`. `want`
    is how many periods the CALLER needs (default `limit`): an answer is
    "short" against that, not against the padded request — otherwise a
    12-year ask padded to 24 re-asks for nearly every company (critic).
    """
    endpoint = ENDPOINTS[statement]

    def ask(params):
        q = {**params, "timeframe": timeframe, "limit": int(limit),
             "sort": "period_end.desc"}
        if since:
            q["period_end.gte"] = since
        body = _get(BASE + endpoint, q, key, symbol=symbol, endpoint=endpoint,
                    timeout=timeout)
        return [r for r in (body.get("results") or []) if isinstance(r, dict)]

    if cik:
        rows = ask({"cik": cik})
        return [r for r in rows if r.get("cik") in (None, cik)], cik
    rows = ask({"tickers": symbol})
    ciks = {r.get("cik") for r in rows if r.get("cik")}
    chosen = _newest_cik(rows)
    if chosen and (len(ciks) > 1 or len(rows) < int(want or limit)):
        again = [r for r in ask({"cik": chosen}) if r.get("cik") in (None, chosen)]
        if len(ciks) > 1 or len(again) > len(rows):
            if len(ciks) > 1:
                log.info("massive_fundamentals: %s spans %d CIKs; re-asked by %s",
                         symbol, len(ciks), chosen)
            rows = again
    return rows, chosen


def _index(label: tuple) -> int:
    fy, fq = label
    return fy * 4 + ((fq - 1) if isinstance(fq, int) else 3)


def _spine(rows: list, timeframe: str) -> dict:
    """{label: row} for the SPINE statement — one row per fiscal period.

    A label with two rows keeps the one whose date no OTHER label claims (the
    other is a stray comparative — see `_attach`), then the later filing. A
    date still claimed by two labels keeps only the label(s) whose date is in
    order with the neighbouring fiscal periods; if that does not single one
    out, NEITHER is kept — a wrong fiscal index is worse than a hole
    (`canslim._period_index`'s rule).
    """
    cands: dict = {}
    labels_on: dict = {}
    for r in rows:
        lab, d = _label(r, timeframe), _day(r.get("period_end"))
        if lab is None or d is None:
            continue
        cands.setdefault(lab, []).append((d, r))
        labels_on.setdefault(d, set()).add(lab)

    out: dict = {}
    for lab, cs in cands.items():
        if len(cs) > 1:
            own = [(d, r) for d, r in cs if labels_on[d] == {lab}]
            cs = own or cs
        pick = None
        for d, r in cs:
            if pick is None or _newer_filing(r, pick[1]):
                pick = (d, r)
        out[lab] = pick

    by_day: dict = {}
    for lab, (d, r) in out.items():
        by_day.setdefault(d, []).append(lab)
    for d, labs in by_day.items():
        if len(labs) < 2:
            continue
        rest = sorted((lab for lab in out if lab not in labs), key=_index)

        def in_order(lab):
            before = [out[x][0] for x in rest if _index(x) < _index(lab)]
            after = [out[x][0] for x in rest if _index(x) > _index(lab)]
            return all(b < d for b in before) and all(a > d for a in after)

        ok = [lab for lab in labs if in_order(lab)]
        for lab in labs:
            if len(ok) != 1 or lab != ok[0]:
                out.pop(lab, None)
    return {lab: r for lab, (d, r) in out.items()}


def _attach(spine: dict, rows: list, timeframe: str) -> dict:
    """{label: row} — each spine period's row from ANOTHER statement.

    JOINED ON THE SPINE'S PERIOD, NEVER ON THE OTHER STATEMENT'S OWN KEY
    (critic 2026-09-30). v1 balance sheets carry prior-year-end COMPARATIVES
    under a wrong label: PEP answers `2025-12-27 FY2025 Q1` beside the real
    `2025-12-27 FY2025 Q4` and the real Q1 at 2025-03-22. Keyed on its own
    (date, label) the stray row became a balance-only "Q1" that sorted ahead of
    the real one, and after `qoq` alignment PEP, DPZ and TER read EPS None in
    the Q1 slot — CANSLIM C refused all Q1 season. Annual rows drift too: CARR's
    FY2021 balance sheet ends 2022-01-04 against the income statement's
    2021-12-31.

    So a row attaches to the spine period whose `period_end` it is nearest,
    within `capital_returns.SAME_QUARTER_DAYS` (nearest-quarter rounding —
    definitional, reused by name); a row whose label matches beats one that
    does not, then the nearer date, then the later filing. A row near no spine
    period attaches to nothing.
    """
    from sepa.capital_returns import SAME_QUARTER_DAYS
    ends = {lab: _day(r.get("period_end")) for lab, r in spine.items()}
    best: dict = {}
    for r in rows:
        d = _day(r.get("period_end"))
        if d is None:
            continue
        lab_r = _label(r, timeframe)
        for lab, e in ends.items():
            gap = abs((d - e).days)
            if gap > SAME_QUARTER_DAYS:
                continue
            rank = (0 if lab_r == lab else 1, gap)
            cur = best.get(lab)
            if cur is None or rank < cur[0] or (rank == cur[0] and _newer_filing(r, cur[1])):
                best[lab] = (rank, r)
    return {lab: r for lab, (rank, r) in best.items()}


def to_vx_report(label: tuple, parts: dict, timeframe: str,
                 statements: Iterable[str] = (), *, symbol: str = "") -> dict:
    """One vX-shaped report from the v1 rows of one fiscal period.

    `parts` maps statement -> the v1 row for this period; the SPINE row's
    `period_end` is the period's date. A requested statement with no row for
    this period comes back as an EMPTY block, never a zeroed one. Only mapped
    lines are emitted, and an absent line is OMITTED rather than written as a
    zero — the vX convention every consumer already handles.

    The INCOME block's `revenues` is the line `revenue_line` chooses for the
    row's template (semantic change 7); the report says which in
    `revenue_line` / `revenue_line_note` (only when INCOME is in `parts`).
    `symbol` is the caller's ticker, carried for provenance only.
    """
    fy, fq = label
    statements = tuple(statements)
    spine_st = statements[0] if statements else next(iter(parts))
    meta = parts.get(spine_st) or next(iter(parts.values()))
    fin = {st: {} for st in statements}
    line_meta: dict = {}
    for statement, row in parts.items():
        blob = {}
        for vx_key, v1_key in FIELD_MAP[statement].items():
            c = _cell(_value(row.get(v1_key)))
            if c is not None:
                blob[vx_key] = c
        for vx_key, addends in DERIVED.get(statement, {}).items():
            raw = [row.get(a) for a in addends]
            if raw[0] is None:
                continue
            try:
                total = sum(float(x or 0.0) for x in raw)
            except (TypeError, ValueError):
                continue
            c = _cell(_value(total))
            if c is not None:
                blob[vx_key] = c
        if statement == INCOME:
            v, line, note = revenue_line(row, cik=meta.get("cik"))
            blob.pop("revenues", None)
            if v is not None:
                blob["revenues"] = _cell(v)
            line_meta = {"revenue_line": line, "revenue_line_note": note}
        fin[statement] = blob
    # The most recent filing that carried ANY of this period's statements.
    filed = max((str(r.get("filing_date")) for r in parts.values()
                 if r.get("filing_date")), default=None)
    quarterly = timeframe == "quarterly"
    derived_q4 = quarterly and fq == 4
    return {
        "fiscal_year": fy,
        "fiscal_period": (f"Q{fq}" if quarterly else "FY"),
        "timeframe": timeframe,
        "end_date": str(meta.get("period_end"))[:10],
        # See semantic change 2: a quarterly Q4 is derived and says so the way
        # vX did. The v1 stamp is kept beside it, never thrown away.
        "filing_date": None if derived_q4 else filed,
        "v1_filing_date": filed,
        "cik": meta.get("cik"),
        "tickers": meta.get("tickers"),
        "source": "massive_v1",
        **line_meta,
        "financials": fin,
    }


def fetch_reports(symbol: str, *, timeframe: str, limit: int,
                  statements: Iterable[str] = ALL_STATEMENTS,
                  timeout: float = 12.0, key: Optional[str] = None) -> list:
    """vX-shaped reports for one company, newest fiscal period first.

    The INCOME statement is the spine (every caller reads it): its rows define
    the fiscal periods, and the balance sheet / cash flow attach to them — see
    `_attach` for why they are never keyed on their own labels. Those two are
    asked from the spine's oldest period onward. Every statement is asked for
    twice the limit, so the stray comparative rows v1 carries cannot crowd a
    real period out; the answer is then cut back to `limit` periods.

    [] means the provider answered and has no filings for this ticker.
    Raises `FinancialsUnavailable` for anything else — see the module docstring.
    """
    if timeframe not in ("quarterly", "annual"):
        raise ValueError(f"timeframe must be quarterly or annual, not {timeframe!r}")
    sym = str(symbol or "").upper().strip()
    statements = tuple(statements)
    unknown = [s for s in statements if s not in ENDPOINTS]
    if unknown or not statements:
        raise ValueError(f"unknown statements {unknown or statements!r}")
    if key is None:
        from massive_keys import stocks_key
        key = stocks_key()
    if not key:
        raise FinancialsUnavailable("no_key", symbol=sym)

    from sepa.capital_returns import SAME_QUARTER_DAYS
    # Income first: it is the spine. Asked with twice the limit too — a stray
    # comparative row in the spine itself would otherwise crowd the oldest
    # real period out of the answer (`_spine` then drops the stray).
    statements = tuple(sorted(statements, key=lambda st: st != INCOME))
    rows, cik = fetch_statement(sym, statements[0], timeframe=timeframe,
                                limit=2 * int(limit), key=key, timeout=timeout,
                                want=int(limit))
    spine = _spine(rows, timeframe)
    labels = sorted(spine, key=lambda lab: _day(spine[lab]["period_end"]),
                    reverse=True)[:int(limit)]
    spine = {lab: spine[lab] for lab in labels}
    if not spine:
        return []
    parts = {lab: {statements[0]: spine[lab]} for lab in labels}
    oldest = min(_day(r["period_end"]) for r in spine.values())
    since = (oldest - timedelta(days=SAME_QUARTER_DAYS)).isoformat()
    for statement in statements[1:]:
        other, cik = fetch_statement(sym, statement, timeframe=timeframe,
                                     limit=2 * int(limit), key=key,
                                     timeout=timeout, cik=cik, since=since)
        for lab, r in _attach(spine, other, timeframe).items():
            parts[lab][statement] = r
    return [to_vx_report(lab, parts[lab], timeframe, statements, symbol=sym) for lab in labels]


def derive_q4_eps(quarterly: list, annual: list) -> list:
    """Quarterly Q4 EPS as ANNUAL minus Q1+Q2+Q3 — the way vX derived it.

    Critic 2026-09-30, measured: v1's Q4 EPS is the derived Q4 net income over
    the derived Q4 SHARE COUNT, and that share count is the one semantic change
    2 already calls broken — NVDA FY2024 Q4 reads 0.26 on v1 against 0.49
    (split-adjusted vX); NFLX FY2024 Q4 0.11 against ~0.43; 13 of 176 Q4s in a
    70-name sample are off by more than 25%. vX served annual − (Q1+Q2+Q3)
    (its float noise gives it away: NVDA FY2026 Q4 = 1.7600000000000002), and
    CANSLIM C and the earnings-quality series were built on that. So this puts
    back exactly that arithmetic — no threshold, no new number. v1 is
    split-consistent across the annual and quarterly rows, which the
    subtraction needs.

    A Q4 whose annual row, or any of whose three quarters, is missing — or
    whose annual period does not end with it (`SAME_QUARTER_DAYS`) — loses its
    EPS (absent), never keeps v1's broken value. Mutates and returns
    `quarterly`; sets `q4_eps_derived` on each Q4 it touched.
    """
    from sepa.capital_returns import SAME_QUARTER_DAYS
    keys = ("diluted_earnings_per_share", "basic_earnings_per_share")

    def eps(r, k):
        if not isinstance(r, dict):
            return None
        return (((r.get("financials") or {}).get(INCOME) or {}).get(k) or {}).get("value")

    ann = {}
    for a in annual or []:
        if isinstance(a, dict) and a.get("fiscal_year") is not None:
            ann.setdefault(a["fiscal_year"], a)
    by = {(r.get("fiscal_year"), r.get("fiscal_period")): r
          for r in quarterly or [] if isinstance(r, dict)}
    for r in quarterly or []:
        if not isinstance(r, dict) or r.get("fiscal_period") != "Q4":
            continue
        fy = r.get("fiscal_year")
        a = ann.get(fy)
        ends_agree = False
        if a is not None:
            da, dq = _day(a.get("end_date")), _day(r.get("end_date"))
            ends_agree = bool(da and dq and abs((da - dq).days) <= SAME_QUARTER_DAYS)
        inc = r.setdefault("financials", {}).setdefault(INCOME, {})
        for k in keys:
            parts = [eps(by.get((fy, f"Q{i}")), k) for i in (1, 2, 3)]
            total = eps(a, k) if ends_agree else None
            if total is None or any(p is None for p in parts):
                inc.pop(k, None)
                continue
            c = _cell(_value(total - sum(parts)))
            if c is None:
                inc.pop(k, None)
            else:
                inc[k] = c
        r["q4_eps_derived"] = True
    return quarterly
