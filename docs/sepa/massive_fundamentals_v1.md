# Massive financials: vX → v1 migration (2026-09-30)

**Why:** Massive's vX financials endpoint answers `Deprecation: true`,
`Sunset: 2026-10-09`, and was already in 410 brownouts on 2026-09-30 (MU and
CRWD 410'd on the probe from the api container; NVDA, SM, ARR answered). Its
`Link` header names the successor, the v1 fundamentals family:

| Statement | v1 endpoint |
|---|---|
| Income statement | `GET /stocks/financials/v1/income-statements` |
| Balance sheet | `GET /stocks/financials/v1/balance-sheets` |
| Cash flow | `GET /stocks/financials/v1/cash-flow-statements` |

Params used: `tickers`, `timeframe` (`quarterly` / `annual`), `limit`,
`sort=period_end.desc`. Auth: `Authorization: Bearer <key>` — the key never
rides in a URL again (verified working 2026-09-30; the repo has leaked the
Massive key five times through URL-bearing exception text).

## One helper, same shape

`backend/sepa/massive_fundamentals.py` is the only module that builds a v1
financials URL (source-guard test). `fetch_reports(symbol, timeframe, limit,
statements)` joins the statements per fiscal period and returns reports in the
**vX shape every consumer already read** for ONE company (the CIK that filed
the newest period, re-asked by `cik=` when a ticker spans several — see the
MU trap below) (`fiscal_year`, `fiscal_period`,
`end_date`, `filing_date`, `financials.{income_statement,balance_sheet,
cash_flow_statement}.<key>.value`), so no downstream formula, alignment or
guard changed.

| Live module | Reads | v1 calls per name |
|---|---|---|
| `sepa/canslim.py` `_fetch_massive_financials` (C/A, sales, earnings quality, qoq) | 15 quarters income + balance (the extra 3 let the OLDEST Q4's EPS be derived, then trimmed to 12); 4 years income | 3 (was 2); +1 when the ticker answer is short of what the caller wants |
| `sepa/longterm.py` `annual_financials` (Fundamentals tab + Sunday warm) | 12 years, all three | 3–4 (was 1) |
| `sepa/board_metrics.py` `_fetch_quarters` → `shares_yoy` + `capital_returns.compute` | 12 quarters, all three | 3 (was 1) |

Each v1 call measured ~0.7 s from the api container (2026-09-30). The Sunday
long-term warm (2,685 names, 6 workers) grows from ~1 to ~3–4 calls per name —
roughly 20 min of fetch, inside its window (an answer is "short" — and
re-asked by CIK — only against the periods the caller wants, not the padded
request). The fetch is sequential per name on
purpose: nested pools inside the warm pools would multiply concurrency against
the provider.

Study scripts under `backend/scripts/` still read vX and are left alone; a
snapshot of the whole vX feed is being saved to
`/Users/ajay/clinet-test/data/massive_vx_financials_2026-09-30/`.

## Field map (every vX key a live module reads)

| Statement | vX key | v1 key | Note |
|---|---|---|---|
| income | `revenues` | per template (2026-10-08): financial = `revenue − cost_of_revenue + other_income_expense`; insurance / standard = `revenue`; CIK picks + hold ledger | see 7 |
| income | `diluted_earnings_per_share` | `diluted_earnings_per_share` | split-adjusted on v1; **quarterly Q4 re-derived** as annual − (Q1+Q2+Q3) in canslim — see 5 |
| income | `basic_earnings_per_share` | `basic_earnings_per_share` | |
| income | `net_income_loss` | `consolidated_net_income_loss` | incl. minority share, as vX |
| income | `net_income_loss_attributable_to_parent` | **derived**: `consolidated_net_income_loss + noncontrolling_interest` | v1 has no parent line; its minority line is the signed adjustment (BX 2,356.1 M − 1,126.9 M = 1,229.2 M). common + preferred dividends was tried first and is wrong for ~5% of names (TDG, OXY, TSN — critic) |
| income | `operating_income_loss` | `operating_income` | |
| income | `gross_profit` | `gross_profit` | |
| income | `income_loss_from_continuing_operations_before_tax` | `income_before_income_taxes` | |
| income | `income_tax_expense_benefit` | `income_taxes` | |
| income | `diluted_average_shares` | `diluted_shares_outstanding` | v1 documents it as the weighted average |
| income | `basic_average_shares` | `basic_shares_outstanding` | |
| balance | `inventory` | `inventories` | |
| balance | `assets` | `total_assets` | |
| balance | `liabilities` | `total_liabilities` | |
| balance | `equity` | `total_equity` | |
| balance | `equity_attributable_to_parent` | `total_equity_attributable_to_parent` | |
| balance | `current_assets` | `total_current_assets` | |
| balance | `current_liabilities` | `total_current_liabilities` | |
| balance | `long_term_debt` | `long_term_debt_and_capital_lease_obligations` | **wider**: includes finance leases; `longterm` stores it for history only, no metric reads it |
| cash flow | `net_cash_flow_from_operating_activities` | `net_cash_from_operating_activities` | |
| cash flow | `net_cash_flow` | `change_in_cash_and_equivalents` | |
| meta | `fiscal_period` (`Q1`..`Q4`/`FY`) | from `fiscal_quarter` + `timeframe` | |
| meta | `end_date` | `period_end` | |
| meta | `filing_date` | `filing_date` | restated — see 3 |

No vX field a live module reads is without a v1 source, so nothing had to be
dropped. v1 also carries a capex line (`purchase_of_property_plant_and_equipment`)
that vX lacked; `capital_returns` still takes capex from yfinance — switching is
a methodology choice left for Ajay.

## Seven semantic changes

1. **v1 zero-fills absent lines.** A line the filing lacks is almost always
   `0.0`, never null (and occasionally the key is missing outright — ARR, DX and
   IOVA's FY2020 annual rows have no `revenue` key). Measured: ARR and DX (mortgage REITs)
   report `income_taxes: 0.0` where vX had no tax line; CRWD, ARR and DX report
   `inventories: 0.0` where vX had no inventory line. Passed through, the REIT
   tax zero would turn `capital_returns`' `no_tax_expense` refusal into a 0 %
   rate and ROIC would silently equal ROCE. **The helper reads an exact 0.0 on
   a mapped line as ABSENT** (the key is omitted, exactly like vX). Accepted
   cost: a genuine $0.00 EPS quarter also reads as unknown.
2. **No derived marker.** vX left `filing_date: None` on a derived Q4 (annual
   minus three 10-Qs) and the board's dilution guard keys on that. v1 stamps Q4
   with the 10-K date, but no 10-Q exists for a Q4, so it is still derived — and
   its share count still breaks (v1 NVDA FY2024 Q4: 47,336,000,000 diluted
   shares vs ~24.9 B either side). **Every quarterly Q4 is emitted with
   `filing_date: None`**; the v1 stamp rides alongside as `v1_filing_date`.
   Annual rows keep their date.
3. **Filing dates are restated.** v1 `filing_date` = the most recent SEC filing
   that carried the period (NVDA FY2026 Q2: 2026-08-26 on v1, 2025-08-27 on vX).
   The latest period's date is still its own filing; older ones move forward.
   Nothing orders or gates on an old period's filing date; the Fundamentals
   tab's per-year `filing_date` will show the later date.
4. **Values are restated.** Split-adjusted (NVDA FY2025 Q1 diluted EPS 0.60 on
   v1 vs 5.98 on vX), rounded on restated comparatives (SM FY2025 Q2 revenue
   793,000,000 vs 792,943,000), and quarters vX omitted are present (vX NVDA
   had no FY2025 Q3). v1 carries **listed names only** — a delisted ticker
   returns an empty list.
5. **v1's quarterly Q4 EPS is broken where its Q4 share count is.** It is the
   derived Q4 net income over the derived Q4 share count (NFLX FY2024 Q4: 0.11
   against ~0.43; 13 of 176 Q4s in a 70-name sample off by > 25% — critic).
   vX served annual − (Q1+Q2+Q3), and CANSLIM C and the earnings-quality
   series were built on it, so `massive_fundamentals.derive_q4_eps` puts back
   exactly that arithmetic (live NFLX FY2024 Q4 → 0.42). A Q4 whose annual row
   or any quarter is missing, or whose annual period ends elsewhere, has NO EPS
   rather than v1's value.
6. **Stray comparative rows, and ticker ≠ company.** v1 balance sheets carry
   prior-year-end comparatives under a wrong label (PEP: `2025-12-27 FY2025
   Q1` beside the real Q4 of that date). Keyed on its own label, the stray
   became a balance-only "Q1" that blanked the real Q1's EPS after alignment —
   CANSLIM C refused for PEP, DPZ, TER in Q1 season (critic, the blocker).
   The **income statement is the spine**: its rows define the periods (a label
   with two dates keeps the one no other label claims; an unresolvable shared
   date is a hole, never a guess) and the balance sheet / cash flow attach to
   the nearest spine period within `SAME_QUARTER_DAYS`, label-match first.
   Every statement is asked for twice the limit so strays cannot crowd a real
   period out. Separately, `tickers=` can span companies (MU also returns CIK
   798287's rows) or come back short for a renamed ticker (SGI: 1 annual row,
   its CIK holds 12): the company is the CIK that filed the newest period, and
   the statement is re-asked by `cik=` whenever the ticker answer spans CIKs
   or is short.

7. **The revenue line follows v1's statement template (2026-10-08).** v1 serves
   three income-statement templates, told apart by KEY PRESENCE (a missing key
   is not a zero-filled one): **financial** (banks, brokers, card lenders —
   neither `interest_expense` nor `research_development` present; MEASURED
   2026-10-07: 380 of 1,409 rows, 38 of 141 names, constant per name),
   **insurance** (`research_development` missing only; 60 rows, 6 names) and
   **standard** (both present, zero-filled; 969 rows, 97 names). On the
   financial template `revenue` is GROSS (interest income + noninterest
   income) and `cost_of_revenue` is total interest expense: BAC Q2-2026 reads
   49,393 M against the 10-Q's "Total revenue, net of interest expense"
   31,558 M (49,393 − 17,835). `revenue_line(row)` therefore returns
   `revenue − cost_of_revenue + other_income_expense` there (C Q2-2026: 24,262
   + 504 = 24,766 M = the 10-Q) and v1 `revenue` everywhere else — an
   insurer's cost line is claims, never netted (TRV 12,153 M, not 12,153 −
   7,708). Six names the verifier reproduced at % AND both levels take a
   CIK-keyed, template-checked pick (`REVENUE_LINE_PICKS`: RKT revenue, LPLA
   revenue + other income, CVS BRO O HPE revenue + interest income); a pick on
   a row of another shape is ignored and says so (`NOTE_PICK_SHAPE_CHANGED`).
   34 more keep their value but carry a note (`REVENUE_LINE_HOLD`: 26
   unverified, 8 his call) so 🛡️ shows them with `*`. A financial-template
   quarter with no cost line is a HOLE (`LINE_UNDETERMINED`, the `revenues`
   cell absent) — never gross revenue (1 row today: STT 2024-06-30). Each
   report carries `revenue_line` / `revenue_line_note`; the cell shape stays
   `{"value": v}`. Quarterly AND annual rows, one engine. The class-wide REIT
   rule (revenue + interest income) was REFUTED (AMT 4.65→5.12, EQIX
   16.36→15.29) and is not in the code. Full record:
   `docs/sepa/revenue_lines_2026_10_08.md`; tests
   `tests/test_massive_fundamentals_v1.py` (the `inc()` fixture now zero-fills
   the standard keys — without that every fixture row read as a bank row).

## Failing loudly

`fetch_reports` returns `[]` only on a 200 with no filings. Everything else
raises `FinancialsUnavailable(reason)`:

| Condition | Behaviour | `reason` |
|---|---|---|
| 410 | raised at once, no retry, WARNING logged | `endpoint_gone` |
| 401 / 403 | raised at once | `not_authorized` |
| 429 / 500 / 502 / 503 / 504 | retried, 3 attempts, 1 s then 2 s (Retry-After honoured, capped at 10 s) | `rate_limited` / `server_error` |
| other status | raised | `http_<code>` |
| connection / timeout | retried, then raised; exception text never kept | `transport_error` |
| non-JSON / `results` not a list | raised | `bad_payload` |
| no key | raised, no call made | `no_key` |

How each module surfaces it:

- **canslim** — `_fetch_massive_financials` keeps its contract (None on
  failure; 401/403 disables Massive for the run; a 429 does not). The reason is
  kept in `_massive_last_error[SYMBOL]`, and the hybrid yfinance fallback / the
  strict path carry it as `_massive_error` on the payload — present only on a
  provider failure, never on "files nothing".
- **longterm** — `metrics()` (and `score_for`) return `ok: false`,
  `error: <code>`, and a reason that says *outage*; the Fundamentals tab
  headlines it "Financial statements unavailable … right now" instead of the
  hard-coded "No filed annual financials" it used to print over ANY `ok:false`.
  "no filed annual financials" now means exactly that. The Sunday
  `longterm.warm` carries a name's prior row forward (`carried_forward`,
  `n_carried_forward`) when its fetch failed on the provider, instead of
  dropping it from the sector pools for a week.
- **board_metrics** — the row carries `financials_error: <code>`; `shares_yoy`
  refuses with `financials_unavailable` (the dilution tooltip explains it —
  `frontend/src/lib/boardMetrics.ts` `DILUTION_BLANK`), and every
  `capital_returns` ratio refuses with `financials_unavailable` (new in
  `capital_returns.REASONS`). `warm()` never overwrites a good cached row with
  an outage row, and an outage row is never "fresh", so the next warm retries.

## Tests

`backend/tests/test_massive_fundamentals_v1.py` (hermetic, no network): the
field map, the parent-NI identity, zero-as-absent, derived Q4, restated dates,
duplicate periods, recycled tickers, 410 / 429 / 5xx / 401 / transport / bad
payload / no key, key-in-header, the PEP stray-row join (helper and through canslim's alignment), spine strays, unresolvable shared dates, CARR's annual drift, the parent-NI identity on TDG/TSN/BX shapes, Q4 EPS derivation and its three refusals, the SGI rename re-ask, the longterm warm carry-forward, and per-module behaviour (canslim end-to-end
through the real helper, split-adjusted A, longterm outage vs empty, board
outage on both readers, the REIT zero-tax regression, the warm
never-overwrites rule) plus two source guards: no live module references the vX
financials endpoint, and only the helper builds a v1 financials URL.

## Old vs new — 24 real names (2026-09-30, pre-market)

Script: `backend/scripts/vx_v1_financials_compare.py` (old = the last vX commit
`0b708d20` against live vX with brownout retries; new = this migration against
live v1; both inside the api container, from `/tmp`, never `/app`). Every
figure below moved by more than 0.5 %; everything not listed agreed.

**Unchanged on every output:** AAPL, MU, HRMY, PLTR.

### CANSLIM C / A (≥ 25 % gates) and board dilution — the real-money inputs

| Name | Field | vX | v1 | Why |
|---|---|---|---|---|
| **SMCI** | A (3-y EPS growth) | −0.55 | **49.99 → A now PASSES** | 10:1 split (2024-10): vX averaged pre-split 11.43 against post-split EPS |
| SMCI | C | 438.71 | 409.09 (pass both) | latest Q is a Q4 (Jun FY-end), derived as annual − Q1..Q3 on both; the year-ago Q4 straddles the 2024-10 split, which vX mixed |
| MSFT | C | 31.78 | 31.51 (pass both) | restated Q1..Q3 EPS rounding inside the derived Q4 |
| **WMT** | A | −5.27 | 24.65 (still < 25) | 3:1 split (2024-02) |
| **CMG** | A | −18.80 | 22.16 (still < 25) | 50:1 split (2024-06) |
| NVDA | A | 192.31 | 271.24 (pass both) | 10:1 split (2024-06) |
| AVGO | A | 71.95 | 83.20 (pass both) | 10:1 split (2024-07) |
| IOVA | A | 6.22 | 23.74 (fail both) | restated annual EPS |
| RKT | A | −58.28 | −12.46 | vX's annual history interleaved **Rock-Tenn** (old RKT ticker, CIK 230498) |
| CRWD | C / A | 103.23 / −229.1 | 114.29 / −493.1 | **4:1 split 2026-07-02** — vX mixed ~250 M and ~1,000 M share bases |
| **BRK.B** | C / A | None / None | **107.85 / 165.66 (both pass)** | vX carried no diluted EPS for Berkshire |
| CRWV | C | None | −90.00 (fail) | v1 carries the pre-IPO year-ago quarter; vX did not |
| ASO | A | −6.61 | −9.45 | restated annual EPS |
| ARR / DX | rev growth (not gated) | 132.05 / 305.5 | None / None | v1 has no `revenue` line for mortgage REITs (0.0 → absent) |
| SM | rev growth (not gated) | 215.28 | 182.22 | v1 revenue 2,238 M vs vX 2,500 M for FY2026 Q2 — a line-definition difference |
| CRWD | dilution | blank (`unstable_share_basis`) | +4.5 % | the split made vX's series jump 4x; v1 is split-adjusted |
| IOVA | dilution | blank (`split_suspected`) | +34.6 % | vX share counts disagreed with live shares by > 3x |
| CRWV | dilution | blank (`no_year_ago_quarter`) | +13.1 % | year-ago quarter present on v1 |
| BRK.B | dilution | blank | −0.1 % | |

C/A gate flips: **SMCI A fail → pass; BRK.B C and A unknown → pass.** No name
went from pass to fail.

### Return on capital (board) and the Fundamentals tab

- **Holes filled** — ORCL, ASO, IOVA had no ROCE/ROIC/ROE on vX
  (`incomplete_ttm_window`: vX omitted quarters); v1 fills them (ORCL ROCE
  11.64 %, ASO 14.11 %, IOVA −37.97 %).
- **Line definitions differ for financials** — BRK.B TTM EBIT 57.9 B → 31.5 B
  (ROCE 4.48 → 2.73), ARR/DX operating income flips sign (ROCE +1.7/+2.3 →
  −3.0/−2.7). All three are `NON_OPERATING_SECTORS`: the boards already show
  them as n/a and do not rank them.
- **SM** ROCE 13.6 → 14.09 (TTM revenue 5.50 B → 5.23 B, EBIT 1.63 B → 1.69 B);
  **LLY** OPM 39.48 → 40.35; **CMG** effective tax 25.5 % → 24.1 %. ROE on
  names with a minority interest (SMCI) matches vX again once parent net
  income is consolidated + the minority adjustment.
- **NTSK** ROE blank (`negative_equity`) → −470 %: v1 carries only the four
  post-IPO quarters, all with positive equity (~157 M against a ~737 M TTM
  loss); vX's extra pre-IPO quarter had negative equity.
- **History length** — AVGO 12 → 8 years and RKT 10 → 8: vX was stitching
  predecessor / unrelated CIKs into the ticker's history (AVGO: Broadcom Ltd
  649338 and Avago 441634; RKT: Rock-Tenn). v1 serves only the current
  company. The other way round, **META 4 → 12** (vX only knew the ticker after
  the FB rename; asking by CIK recovers the years), GOOGL 10 → 11, IOVA
  7 → 11. CAGRs move accordingly (AVGO sales 19.1 → 17.4 %, RKT sales 9.3 →
  6.5 %, META sales 19.9 → 24.7 %, profit 37.6 → 21.8 %).
- **Restated comparatives** move 10-year CAGRs slightly: MSFT sales 15.61 →
  14.70 %, profit 22.71 → 20.22 %; SMCI sales 39.2 → 35.8 %.
- **`coverage.filing_date`** is now the latest filing that carried the fiscal
  year (LLY FY2025: 2026-02-12 → 2026-08-05). The tab labels it "latest
  filing", with a tooltip saying why.

### A trap found by this comparison (fixed before shipping)

`tickers=MU` on v1 answers annual rows from **two** companies (Micron and CIK
798287, a ~$500 M-revenue filer). Keeping only Micron's rows first left it 9
years where it has 12; the helper now picks the company that filed the newest
period and re-asks by `cik=`, and MU matches vX exactly.
