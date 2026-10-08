# Revenue lines per v1 statement template (2026-10-08)

Ajay 2026-10-08, asked "Want those ranked?" about the 141 names held out of the 10-07 heal: *"update them please"*.

## Why

Massive v1 serves a bank's `revenue` GROSS — interest income plus noninterest income — with total interest expense as
`cost_of_revenue`. BAC Q2-2026: v1 49,393 M; the 10-Q's "Total revenue, net of interest expense" 31,558 M
(49,393 − 17,835). A research refresh with no fix ranks BAC at +3.67 % where the 10-Q says +14.99 %. The vX-era stored
figures are not the answer either: vX sunsets 2026-10-09 and the stored % matches the 10-Q for only 62 of 139.

## Template detection (MEASURED, 1,409 raw quarterly rows, 141 names)

v1 rows come in three templates, told apart by KEY PRESENCE — a missing key is not a zero-filled one:

| template | `interest_expense` key | `research_development` key | rows | names |
|---|---|---|---|---|
| financial (banks / brokers / card / lenders) | missing | missing | 380 | 38 |
| insurance | present | missing | 60 | 6 |
| standard | present (0.0 when absent) | present (0.0) | 969 | 97 |

The template is constant per name across all 10 rows of every name. Financial template: `revenue − cost_of_revenue +
other_income_expense` (other income 0 when absent) = the 10-Q's total net revenue; C Q2-2026 24,262 + 504 = 24,766 M.
Insurance / standard: v1 `revenue` (an insurer's cost line is claims — TRV 12,153 M is the 10-Q, not 12,153 − 7,708).

Code: `backend/sepa/massive_fundamentals.py` — `row_template`, `revenue_line`, `REVENUE_LINE_PICKS`,
`REVENUE_LINE_HOLD` (semantic change 7). Persistence: `canslim._one_revenue_line` → `fundamentals.rev_line`,
`rev_line_series`, `rev_line_note`, `rev_line_mixed`. Surface: 🛡️ `growth_read` (`line_unverified`, `line_mixed`,
class `revenue_line`).

## One table, one denominator

`revenue_lines_2026_10_08.csv` (this folder) = the R-file table (`ta_match_table`: the face of each latest 10-Q and its
own same-filing year-ago; 139 of 141 have a face line — NU is an IFRS foreign filer, NLY prints no revenue line) plus
`spec_line` (the helper's line on the latest row) and `spec_status`. Match = % within 0.10 pp OR both quarter levels
within 0.2 % (representation tolerances of the measurement, not rules).

| figure | matches the 10-Q | |
|---|---|---|
| stored % on 10-07 (vX era, shown `*`) | **62 / 139** | MEASURED |
| plain v1 `revenue` (a refresh with no fix) | **68 / 139** | MEASURED |
| this change — ranked | **107 / 107** (99 on % and levels; CI PAYX CNC STZ MOH EVR on % only; CB 0.16 pp and YUM 0.11 pp on levels only); **0 ranked on a figure the 10-Q contradicts** | MEASURED (dry run 2026-10-08, 0 Massive calls) |
| this change — shown `*`, not ranked | 26 unverified + 8 his call = 34 | — |

Cross-check (SEC companyfacts, 52 held + 10 non-held): the template rule + other income reproduces JPM BAC WFC PNC TFC
FITB AXP COF SYF C GS SCHW OMF and non-held MS CFG HWC. A class-wide REIT / insurer rule (revenue + interest income) was
REFUTED — AMT 4.65 → 5.12, EQIX 16.36 → 15.29, both right today — and is not in the code.

## Per-name outcome (141)

- **RULE `net_of_interest`, ranked (34):** AXP BAC BPOP C CFR COF COLB EWBC FCNCA FHB FHN FITB FNB GS HBAN JPM KEY MTB
  NTRS OMF PB PNC RF SCHW SLM SSB STT SYF TFC USB WAL WFC WTFC ZION.
- **PICK, ranked (6), keyed by CIK and checked against the template it was measured on:** RKT revenue (2,784 / 1,451 M
  "Total revenue, net"), LPLA revenue + other income (5,186.6 M), CVS BRO O HPE revenue + interest income (106,096 /
  1,676 / 1,547.0 vs 1,547.7 / 12,213 M). A pick on a row of another shape is ignored and the note says re-check it.
- **PLAIN `revenue`, ranked (67):** CPT EQIX PLD RITM EVR HLI NDAQ OWL DHR GE MMM NOV OXY AIG AJG CB CI CNC ELV HIG MKL MOH
  APTV BDX BWXT CBRE CHDN CORT CSGP CTSH DAL EFX ETSY FAST FDX FLS GM GPC GPN GRMN HAS IFF ISRG LAD LII LKQ MAS MCD MIDD
  MSCI NOC NTAP PAYX PEGA QXO RBLX RSG STZ UAL WAT YUM ZTS AWK DUK NEE NI SRE.
- **HOLD, unverified (26)** — value kept, shown `*` with the reason:
  - no net-interest-income line (fee sub-line): SOFI, IBKR;
  - drops income the 10-Q's total includes: BX, APO, VIRT, AFRM, WELL;
  - 10-Q total is after operating-lease depreciation: ALLY;
  - foreign filer, no quarterly XBRL: NU;
  - the 10-Q prints no revenue line: NLY;
  - matches no line on the 10-Q: EOG, EXE, OVV, AM, LAZ, ELS, DLTR, MP, CERS;
  - revenue + interest-income pick measured, not cross-checked: DOC, NNN, REXR, STWD, SUI, VTR, CNH.
- **HOLD, his call (8)** — sub-line of the 10-Q (sales before other income, or one segment): CVX DVN RRC MTDR APA SNA DVA EPR.

Before → after on the 10-Q quarter (stored → plain v1 → this change, MEASURED dry run): BAC 19.25 → 3.67 → **14.99**;
JPM 27.69 → 17.89 → **27.69**; GS 39.46 → 22.91 → **39.46**; C 14.30 → 5.83 → **14.30**; GE 24.73 → 21.10 → **21.10**;
NEE 4.69 → 12.45 → **12.45**; CVX 56.30 → 51.43 → 51.43* (held, his call); SOFI 1.11 → 27.35 → 27.35* (held).

## Consumers that move (all INTENDED — filing-correct input; no gate or threshold touched)

Dry run, 141 held names, this change vs a no-fix refresh: sales tier 21 flips; the Bonde pillar / demand-board gate /
catalyst-lane `sales_gate` / knife watch 13, all fail → pass (BAC USB TFC STT MTB KEY EWBC FHN BPOP ALLY CFR FNB FHB);
desk catalyst points 24; earnings-quality net margin 40. Against TODAY's stored docs: tier 45, Bonde pass 25,
demand gate 22, 🛡️ sales ranked 107. 🚀 growth board loses NLY and RKT with or without the fix. Universe (INFERRED, SEC-frames
proxy): ~296 bank-style filers, ~61 more demand/catalyst/knife gate flips mostly fail → pass.

## HIS CALL

- **H1** the 8 sub-line names: rank on v1's sub-line, on the 10-Q total (only CVX reproducible), or keep `*` (SHIPPED
  DEFAULT). While pending the trading gates read v1's line: RRC +8.57 vs 10-Q −2.65 and APA +8.95 vs −8.15 sit on
  opposite sides of the 5 % floor.
- **H2** promote the 7 revenue + interest-income picks (DOC NNN REXR STWD SUI VTR CNH) and PGR (non-held, revenue + other
  income 7.29 vs plain 6.40)? Default: not promoted.
- **H3** the template rule is universe-wide (one engine) — ~261 more bank filers; default heal them now.
- **H4** a bank-template quarter with no interest-expense line → a hole (default) vs as-reported revenue. Reach today:
  1 row (STT 2024-06-30, slot 8).
- **H5** a monthly audit cron line (host crontab, not shipped by a deploy).

Edit the picks / ledger only in `massive_fundamentals.REVENUE_LINE_PICKS` / `REVENUE_LINE_HOLD`.

## How to re-run

1. Audit (read-only, SEC companyfacts, 0 Massive calls; `block_writes()` first):
   `python scripts/revenue_line_audit.py --held --financial --out /out/revenue_line_audit.json`. Verdicts: match /
   mismatch / unchecked (companyfacts lags — C sat at 2025-09-30 on 10-07 — is unchecked, never mismatch). Where a
   companyfacts tag is not the face line (MTB, CPT, RSG, HAS) the R-file face is the arbiter.
2. Dry run (§5.2 of the spec): stub `MF._get` with the saved raw rows, run `canslim._fetch_massive_financials` and
   `resiliency_tab.growth_read` per name; PASS = the table above.
3. Durability: after the Q3-2026 10-Qs land (banks ≈ early November) run step 1 once; the template rule must reproduce
   the new quarter with no code change (0 mismatches on ranked names).
