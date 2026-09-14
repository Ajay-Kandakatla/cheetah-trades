# Long-term fundamentals — the ten metrics and the sector score

**Shipped 2026-09-14.** Ticker page ▸ **Fundamentals** tab, above the CANSLIM block.

## Where this came from

Ajay sent a ten-row checklist screenshot — OPM, EPS, D/E, ROE, ROCE, Net Profit,
Promoter Holding, Cash Flow, Balance Sheet, 10 Year Sales & Profit Growth — with
*"Can you add these metric, I know some of the stocks may not have 10 years."*

I pushed back on putting ten more chips on an already-dense tile (Rule #5). He
relocated it himself: *"Move them to fundamentals tab in the individual ticker
and give a score on the fundamentals ranking for longterm."*

## This score is NOT from a book

I asked whether the checklist came from a source I should build to. It does not.
So the weights are **mine**, and every surface says so.

This matters because of the SEPA scope boundary: Minervini (SEPA), O'Neil
(CANSLIM) and Kell each own their own cited formulas, and **none of them is the
authority for a long-term quality score**. This module cites nobody.

`SCORE_IS_MEASURED = False` in `backend/sepa/longterm.py` is the switch that
governs the frontend's language. While it is false the tab describes what the
filings say and never predicts what the stock will do. **Do not flip it without
a committed, re-runnable study with a confidence interval** — three boards this
year (Hot Pullback, KC Coiled, Bonde) shipped a claim that later measured null
or inverted.

## Data source

One endpoint: Massive `/vX/reference/financials?timeframe=annual`. Income
statement, balance sheet and cash-flow statement per fiscal year, as filed.

| | |
|---|---|
| AAPL | 17 filed years available (2009–2025), 12 kept |
| CRWD | 7 years |
| NTSK | 1 year (IPO 2025-09-18) |
| Universe warm | 2,685 scanned · 1,979 with filings · 1,773 ranked |
| No filings | 706 — ETFs, trusts, many foreign issuers |

Nothing is scraped, estimated, interpolated or carried forward. A missing line
item makes the metric `None` and the tab says which of the two reasons it is.

## The metrics

| Metric | Formula |
|---|---|
| OPM | `operating_income_loss / revenues` |
| EPS | `diluted_earnings_per_share` |
| D/E | `liabilities / equity` — **total** liabilities, not just `long_term_debt` |
| ROE | `net_income_attributable_to_parent / equity` |
| ROCE | `operating_income_loss / (assets − current_liabilities)` |
| Net profit | `net_income_loss_attributable_to_parent` |
| Cash flow | `net_cash_flow_from_operating_activities` |
| Cash conversion | `ocf / net_income` |
| Current ratio | `current_assets / current_liabilities` |
| 10y sales growth | revenue CAGR over the filed span |
| 10y profit growth | net-income CAGR over the filed span |

**D/E uses total liabilities on purpose.** A company funded by payables and
leases is levered whether or not it issued a bond; `long_term_debt` alone grades
that name as pristine.

## "Promoter Holding" has no US equivalent

Promoter holding is an Indian exchange disclosure — the founding group's stake.
US issuers file nothing of the kind. Ajay's call when I raised it: *"Yeah check
for any institutional volume yourself."*

The slot is filled by two readings that are **kept apart**, never blended:

- `ownership_pct` — the **level**: institutional holding via
  `canslim.fundamentals_for` (yfinance `heldPercentInstitutions`).
- `block_share_pct` — the **flow**: share of the last session's volume printed
  in blocks of 5,000+, off the consolidated trade tape.

Rule #7: a level is never a flow. The tab labels the row **Institutional** and
explains the substitution rather than showing a different number under his
original label.

## The score

Every metric is percentiled **within the stock's own GICS sector** (Ajay's
choice). ROCE and D/E are not comparable between a bank and a software company;
one universe-wide ranking would score the sector, not the company.

| Weight | |
|---|---|
| `roce` | 18% |
| `sales_cagr` | 14% |
| `profit_cagr` | 14% |
| `roe` | 12% |
| `opm` | 12% |
| `de` (inverted) | 12% |
| `cash_conv` | 10% |
| `inst` | 8% |

### Two guards that are the whole point

**1. Absence is not always ignorance.** `profit_cagr` and `cash_conv` go blank
for two different reasons, and treating them the same **flatters loss-making
companies**:

- *no history* (NTSK, one filed year) — genuinely unknown. Dropped, remaining
  weights renormalised.
- *loss* — the company lost money, so there is no CAGR and no earnings for cash
  to convert. **That is the answer, not a gap.** It scores `LOSS_PERCENTILE`
  (10) and votes.

Without this, a cash-burning story is graded only on the metrics it happens to
be good at. Measured effect on the Technology pool: SNOW 24.1 → 20.7, MSTR
17.4 → 15.6, INTC 16.3 → 14.8.

**2. A thin score is not ranked.** `MIN_COVERED_WEIGHT = 0.70`. DDOG scored 74.2
on **0.34** of the weights and sat third in Technology; it now reports
`ranked: false` with its reason. Chosen from the real distribution — the median
name covers 1.00 and 97% cover ≥ 0.70.

A sector needs `MIN_SECTOR_N = 20` priced peers before it ranks anything.

## Bug found while building this

`_cagr` originally filtered `None` holes out and then used `len(vals) - 1` as
the span. That **compresses the timeline**: a company with one missing filing
across `100 → [gap] → 121 → 133.1` annualised over 2 periods and reported
**15.37%** where the truth over 3 periods is **10.0%**. The span is now measured
between the first and last reported index. Pinned by
`test_cagr_ignores_none_holes`.

## Where it runs

| | |
|---|---|
| Cross-section | `20 6 * * 0` — Sunday 06:20 ET, `python -m sepa.longterm warm` |
| Not holiday-gated | filed financials don't move intraday; the gate would skip Sunday |
| Endpoint | `GET /sepa/longterm/{symbol}` |
| Mongo | `longterm_fundamentals`, one doc `latest` |
| Backend | `backend/sepa/longterm.py` |
| Frontend | `frontend/src/components/LongTermFundamentals.tsx` |
| Tests | `backend/tests/test_longterm_fundamentals.py` (30) · `frontend/src/components/LongTermFundamentals.test.tsx` (12) |

`block_share_pct` is deliberately **not** called during the warm — it pages the
raw trade tape, and doing that across 2,685 names would hammer a provider
already observed refusing connections under burst load (297 chunk failures in
one rotation rebuild, 2026-09-14). It is a per-symbol read on the ticker page.

## Still owed

- **The study.** Does the score predict forward returns, against a
  sector-matched placebo? Until that exists with a CI, `SCORE_IS_MEASURED`
  stays `False` and the tab makes no forward claim.
