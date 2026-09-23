# Return on capital — the data layer behind the quality read

**Ajay, 2026-09-22:** *"Where we look at quality I need filter tab in explosive
growth tab, whcih manage quality like very less capital and hi ROI."*

Quality here means **low capital employed, high return on it**. Before this
work the app could not compute a return on capital at all. This document
covers WP-1 — the data layer. It ships no surface and changes no existing
selection.

> **This read is NOT measured.** `capital_returns.MEASURED = False`, and every
> served row carries `capital_measured: false`. Every figure below is an
> ACCOUNTING IDENTITY computed from filed statements — arithmetic, not an edge.
> Nothing here has been shown to predict a return, and no threshold in it has
> been fitted to an outcome. **It is a screen.** The house precedent is
> `sepa/longterm.py:105`, which ships `SCORE_IS_MEASURED = False` for the same
> reason; this module neither borrows that score's credibility nor lends it any.

---

## Where it lives

| Thing | Path |
|---|---|
| Computation (pure, no I/O) | `backend/sepa/capital_returns.py` |
| Fetch + store + flatten | `backend/sepa/board_metrics.py` |
| Mongo collection | `board_metrics` (existing, 36 h TTL) |
| Tests | `backend/tests/test_capital_returns.py` |

**No second provider path and no second collection.** The Massive
`/vX/reference/financials` call that `board_metrics` already makes once per name
per board warm now feeds two readers: `shares_yoy` (reported quarters only) and
`capital_returns` (derived Q4s included — see below). The board read path is
unchanged: `snapshot()` is still ONE Mongo read per board, and nothing fetches
per name on a board request. That rule is why `board_metrics` exists — 80 tiles
× 1 call measured 65 s.

---

## Sources

| Figure | Source | Why |
|---|---|---|
| assets, equity, current liabilities, liabilities | Massive `balance_sheet` | 21/21 on the live board, all from ONE filing |
| operating income (EBIT), net income, revenue, pre-tax income, tax | Massive `income_statement` | 21/21 |
| operating cash flow | Massive `cash_flow_statement` | 21/21 |
| **capex** | **yfinance `quarterly_cashflow`** | **Massive has NO capex line — measured 0/21** |

Massive's cash-flow statement carries 8 aggregate lines and neither
`capital_expenditure` nor `payments_to_acquire_property_plant_equipment`. Its
investing total lumps capex together with acquisitions and securities, so it
cannot be backed out. yfinance carries it at 19/21; the two misses are mortgage
REITs, which have no capex line anywhere.

capex is therefore **the only figure from a second source**, and it arrives
period-stamped precisely so it can be refused rather than mixed (below).

---

## The finding the module turns on: derived Q4s

`board_metrics` drops every quarter whose `filing_date is None` — a **derived
Q4**, annual minus the three reported quarters — because for an AVERAGE SHARE
COUNT that subtraction is nonsense (NVDA's reads −28,000,000).

**That guard must not be inherited here**, and `board_metrics`' own docstring
says why: *"For a flow item that subtraction is fine; for an AVERAGE share
count it is meaningless."* Measured on the 21 live growth names, 2026-09-22:

| TTM window built from | Names with 4 consecutive quarters |
|---|---|
| REPORTED quarters only | **1 / 21** |
| including derived Q4 | **21 / 21** |

Almost every company's Q4 is derived, so a reported-only window is empty for 20
of 21 names. The reconstruction was **verified against an independent source**
rather than assumed:

```
NVDA TTM revenue, summed from Massive quarters   302,969 M
yfinance .info.totalRevenue (independent TTM)    302,970 M
```

To the dollar. 13 of 21 agree within 1%. The eight that do not are dominated by
mortgage REITs and financials (DX −50.8%, ARR −51.8%, NLY −58.0%), where the two
sources define "revenue" differently — exactly the cohort
`board_metrics.NON_OPERATING_SECTORS` already tells the boards not to rank.

**Balance-sheet values inside a derived Q4 are real, not subtracted.** Checked
before relying on them: NVDA's derived Q4 2026 reports assets 206,803 M, sitting
monotonically between reported Q3 2026 (161,148 M) and Q1 2027 (259,474 M). The
provider carries the point-in-time balance sheet through; only flow lines are
reconstructed. Same on MU and SITM.

A derived row can still carry no flow data at all (NVDA Q4 2025 reports
`revenues: None`), so `ttm_sum` returns None the moment any quarter lacks its
line. It never sums three quarters and calls it four.

---

## Formulas, and the definition each follows

**Capital employed = total assets − current liabilities.**
The classic ROCE denominator, identical to equity + non-current liabilities.
Chosen over *total debt + equity − cash* because every input comes from the
SAME filing, so the ratio cannot mix quarters. The cash-adjusted variant would
need a cash figure Massive does not carry — it would have to come from
yfinance `.info`, which carries no period stamp at all. **See his-call #1.**

| Field | Formula |
|---|---|
| `roce_pct` | TTM EBIT ÷ average capital employed |
| `roic_pct` | NOPAT ÷ average capital employed, NOPAT = TTM EBIT × (1 − effective tax rate) |
| `roe_pct` | TTM net income ÷ average equity, BOTH on the basis `roe_basis` names |
| `asset_turnover` | TTM revenue ÷ average total assets |
| `capex_intensity_pct` | \|TTM capex\| ÷ TTM revenue |
| `fcf_conversion_pct` | (TTM operating cash flow − \|TTM capex\|) ÷ TTM net income |

**"Average"** is the mean of the balance sheet at the END of the TTM window and
at the end of the quarter BEFORE it — the textbook pairing of a flow measured
over a year against the stock it was earned on. Where that earlier quarter is
absent the ending balance is used instead.

`denominator_basis` reports that choice **per denominator**, not once for the
row:

```json
{"capital_employed": "average", "equity": "ending", "assets": "average"}
```

`ce_avg`, `eq_avg` and `assets_avg` each fall back on their own, so a single
flag taken off the capital-employed leg told the reader an average was used on
a ROE computed off the ending balance. It is the field a reader would use to
decide whether two names' figures are comparable, so it says what actually
happened to each one.

**`roe_basis`** is the same courtesy for the other half of ROE. It is
`"parent"` only when the filings carry BOTH the parent net-income line and the
parent equity line; otherwise both legs are consolidated, and a missing
consolidated line is a refusal. Letting the numerator and denominator fall back
independently is how a filer with minority interests prints the MINORITY'S
earnings over only the PARENT'S equity — a 2.5x overstatement on the synthetic
set that found it. Measured across 71 live names (the 21 board rows plus 50
sampled from `board_metrics`), Massive emits both parent lines or neither, so
today every name resolves the same way it did before.

**ROE also requires the `assets` line**, even though it does not divide by it.
It is the one ratio whose denominator comes from somewhere else, so it was the
one that could reach the divide with nothing to bound it: a 0.01 equity base on
a filing with no assets line printed **40,000,000%**. ROCE and ROIC are already
`None` without assets (capital employed IS assets − current liabilities) and
asset turnover divides by assets itself. ROE now refuses the missing input the
same way. All 71 live names carry the assets line today.

**The effective tax rate comes from the filings themselves**, never a statutory
guess — a statutory rate would be an invented number.

### Independent validation

```
NVDA roe_pct, computed here            117.2 %
yfinance .info.returnOnEquity          117.211 %
```

---

## Guards — a blank is never a zero

Every refusal carries a reason from `capital_returns.REASONS`, the house pattern
copied from `sepa/since_report.py:86`, so a surface can explain an em-dash
instead of leaving the reader to guess.

| Reason | Meaning |
|---|---|
| `no_quarters` / `incomplete_ttm_window` | fewer than 4 consecutive fiscal quarters |
| `missing_input` | a needed line item is absent in the window |
| `negative_capital_employed` | assets − current liabilities ≤ 0 |
| `negative_equity` | equity ≤ 0 |
| `denominator_too_small` | see the sanity bound below |
| `nonpositive_pretax_income` | loss-making year — no honest tax rate |
| `no_tax_expense` | the provider omits the tax line entirely |
| `effective_tax_rate_out_of_range` | a tax benefit, or a rate above 100% |
| `non_operating_sector` | a bank / REIT balance sheet is not this |
| `no_capex` | no capital-expenditure line anywhere |
| `capex_period_mismatch` | capex is from a different fiscal quarter |
| `nonpositive_denominator` | generic guard for a ratio's base |

**The failures these prevent, each pinned by a test:**

- **Negative equity** divided into a negative profit prints a **positive ROE**.
  A company with wiped-out book equity would read as the best name on a quality
  board while being the most damaged one on it.
- **A tiny but positive denominator** is confident and plausible: $2 M of equity
  against $4 B of assets and $80 M of profit is **ROE 4,000%**. The guard for it
  exists and **ships OFF** — see below; blanking that cell turned out to have a
  worse failure mode than printing it.
- **A tax benefit** (negative rate) makes NOPAT *larger* than EBIT, ranking a
  company higher for having lost money somewhere else.
- **Mixed-quarter capex** pairs this quarter's revenue with last quarter's
  capex.

### The sanity bound, and why it ships OFF

`MIN_DENOMINATOR_ASSET_SHARE = 0.0` — **off**. The guard, the
`denominator_too_small` reason and the constant all remain, so setting a value
is one edit and his call.

It was briefly set at `0.01`, and that is the one picked, non-definitional
number this package would have shipped. Review measured what it cost, and the
cost is not a blank cell:

`growth/capital_quality.py` excludes an UNKNOWN component from `answered`, so
suppressing a ratio **can raise a grade**. A company earning **−167% on a
capital base of 0.75% of its assets**:

| bound | `roce_pct` | `positive_roce` | grade |
|---|---|---|---|
| `0.01` | `None` (`denominator_too_small`) | UNKNOWN | **all 3/3** |
| `0.00` (shipped) | `−166.67` | **FAIL** | most 3/4 |

A screen that reads BETTER because a figure was suppressed is worse than no
screen. No live name was ever cited as reaching the bound — the justification
was a synthetic ROE case, and `roe_pct` is not a `capital_quality` component at
all. **See his-call #2.** Pinned by
`test_REGRESSION_a_blanked_ratio_can_UPGRADE_a_capital_destroyers_grade`.

The mirror cost of `0.0` is real and is his to weigh: a near-zero capital base
now produces a huge POSITIVE ROCE and `positive_roce` PASSes instead of going
UNKNOWN. Nobody has measured which error is dearer, so the package ships the
setting that invents nothing.

### Restatements are resolved by filing date

A fiscal quarter filed twice — an original and a restatement — is resolved by
`filing_date`, in `ttm_window` and in the prior-quarter balance-sheet lookup
alike. `_fetch_quarters` sends no `sort` parameter, so the provider's list order
is its default and not a guarantee; left to it the SAME company printed two
different ROCEs depending on which copy came first, and with a negative restated
EBIT `positive_roce` — a graded chip and a pushed alert — flipped on the same
evidence. A filing date is a filed fact, not a chosen number. A derived Q4
carries no filing date and sorts behind a reported filing of the same quarter.

Measured 2026-09-22 across 71 live names: **zero** `(fiscal_year,
fiscal_period)` collisions. Massive is not currently returning amended filings
as separate rows, so this was latent, not live.

Everything else is definitional: a denominator must be positive, a tax rate must
lie in [0, 1], a window must have four quarters.

---

## Period reporting (Rule #7)

Every row carries the as-of **PERIOD**, never the cache age:

- `capital_period` — e.g. `"Q2 2026"`
- `capital_period_end` — e.g. `"2026-06-30"`
- `capital_period_is_derived` — whether the latest quarter is a derived Q4
- `capital_period_mismatch` — **does the balance sheet's quarter agree with the
  growth board's own `period_end`?**

A balance sheet drawn from a different quarter than the growth figures beside it
is a real defect, not a cosmetic inconsistency: every ratio on the row would pair
a numerator and a denominator from different points in time.

`SAME_QUARTER_DAYS = 45` decides agreement. Two period-ends belong to the same
quarter when they are nearer to each other than to the neighbouring quarter-end;
a quarter is ~91 days, so the midpoint is ~45. **This is nearest-quarter
rounding — definitional, not tuned.** It exists because two providers stamp the
same quarter days apart (MU: Massive `2026-05-28` vs yfinance `2026-05-31`)
while a genuinely stale source is a whole quarter off (NLY: Massive
`2026-03-31` vs yfinance `2026-06-30`).

**Measured 2026-09-22: 0 of 21 rows disagree today** — which is exactly why the
check has to be automatic rather than eyeballed once.

---

## Measured coverage — live growth board, 2026-09-22

21 rows. **5 are non-operating** (HHH, DX, ARR, NLY, RKT — Financial Services /
Real Estate), refused by name rather than rendered as if comparable.

### Stored inputs

| Field | Coverage |
|---|---|
| `capital_employed` | 21/21 (100%) |
| `total_assets` | 21/21 (100%) |
| `total_equity` | 21/21 (100%) |
| `ttm_ebit` | 21/21 (100%) |
| `ttm_revenue` | 21/21 (100%) |
| `ttm_net_income` | 21/21 (100%) |
| `ttm_operating_cash_flow` | 21/21 (100%) |
| `ttm_capex` | 16/21 (76%) |

### Derived fields

| Field | All rows | Of the 16 OPERATING rows |
|---|---|---|
| `roce_pct` | 16/21 (76%) | **16/16 (100%)** |
| `roe_pct` | 16/21 (76%) | **16/16 (100%)** |
| `asset_turnover` | 16/21 (76%) | **16/16 (100%)** |
| `capex_intensity_pct` | 16/21 (76%) | **16/16 (100%)** |
| `fcf_conversion_pct` | 15/21 (71%) | 15/16 (94%) |
| `roic_pct` | **11/21 (52%)** | 11/16 (69%) |

Every refusal is structural, none is a fetch failure:

| Field | Reason | n | Names |
|---|---|---|---|
| all ratios | `non_operating_sector` | 5 | HHH, DX, ARR, NLY, RKT |
| `roic_pct` | `no_tax_expense` | 3 | LQDA, INSW, LPG |
| `roic_pct` | `effective_tax_rate_out_of_range` | 1 | ALAB (tax benefit) |
| `roic_pct` | `nonpositive_pretax_income` | 1 | FF (loss-making) |
| `fcf_conversion_pct` | `nonpositive_denominator` | 1 | FF |

The `no_tax_expense` names are shipping companies under tonnage-tax regimes and
REITs — structurally untaxed, not unfetched.

### What the coverage means for the surface

The repo's own bar is written at `sepa/research.py:154`: *"a column blank for a
third of the board is worse than no column"* — the measured reason `moat`
(64.7%) was kept off the Hottest Sectors table.

- **`roce_pct` at 76% clears that bar** and is the honest headline for "high
  return on capital". It is also PRE-TAX, so it needs no tax assumption.
- **`roic_pct` at 52% does not clear it.** It belongs in a drill-in, not as a
  board column or a sort key. Shipping it as a column would leave half the board
  blank and would quietly penalise REITs and tonnage-taxed shippers for a
  provider gap.

### Live values (operating names)

| | ROCE% | ROIC% | ROE% | aTurn | capex% |
|---|---|---|---|---|---|
| NVDA | 100.4 | 84.3 | 117.2 | 1.31 | 2.4 |
| MU | 64.8 | 55.4 | 66.6 | 0.85 | 28.0 |
| LQDA | 65.9 | — | 131.8 | 1.16 | 4.4 |
| TER | 39.1 | 33.9 | 36.7 | 1.03 | 5.9 |
| INSW | 31.9 | — | 37.4 | 0.45 | 28.9 |
| CRDO | 23.3 | 23.1 | 25.4 | 0.72 | 4.5 |
| LPG | 20.3 | — | 28.3 | 0.32 | 15.6 |
| ALAB | 18.6 | — | 25.8 | 0.75 | 4.9 |
| SM | 13.6 | 10.3 | 16.1 | 0.40 | 35.6 |
| BE | 10.5 | 10.4 | 22.2 | 0.76 | 3.6 |
| PTGX | 7.6 | 7.5 | 11.0 | 0.35 | 0.2 |
| EVC | 6.6 | 3.6 | 4.8 | 1.56 | 1.4 |
| STAA | 3.5 | 0.8 | 1.1 | 0.74 | 1.0 |
| IPI | 1.6 | 1.6 | 5.3 | 0.69 | 7.5 |
| SITM | −1.0 | −1.0 | 1.3 | 0.25 | 9.4 |
| FF | −17.0 | — | −18.4 | 0.71 | 13.8 |

Note the ask's own shape is visible here: **"low capital, high return"**
separates NVDA / LQDA / TER / CRDO (high ROCE, low capex intensity) from
MU / SM / INSW (comparable or high ROCE, but 28–36% capex intensity — they buy
their returns with capital). That contrast is the read he asked for, and it is
only visible now that both legs exist.

---

## His-call items

1. **ROIC denominator.** Shipped as NOPAT ÷ capital employed (assets − current
   liabilities), so every input is from one filing. The other standard
   definition is NOPAT ÷ invested capital (total debt + equity − cash). That
   second one needs a cash figure Massive does not carry, so it would mix a
   yfinance `.info` snapshot with a Massive filing and lose period coherence
   entirely. Flagged rather than silently chosen.
2. **`MIN_DENOMINATOR_ASSET_SHARE` ships at `0.0` — off**, because any positive
   value is a number nobody measured and blanking a ratio can UPGRADE a capital
   destroyer's grade (table above). The guard still works: set a share (0.05,
   say) and every ratio is bounded again. The trade you are choosing is
   *print a meaningless 4,000%* (off) versus *let a suppressed figure improve a
   grade* (on). **Your call, one line.**
3. **`fcf_conversion_pct` denominator.** Shipped as FCF ÷ net income (cash
   conversion of earnings). The common alternatives are FCF ÷ revenue (an FCF
   margin) and FCF ÷ EBITDA. Different question, different number.
4. **ROIC on the surface.** At 52% coverage it should not be a board column or a
   sort key. Recommend drill-in only, with `roce_pct` as the headline.
5. **Averaging basis.** Shipped as the mean of the window's ending and beginning
   balance sheets, falling back to ending-only per denominator with
   `denominator_basis` saying which. Some desks use ending-only always.
6. **ROE's basis.** Shipped parent-only when BOTH parent lines are filed, else
   consolidated for both legs, served as `roe_basis`. A desk that always wants
   consolidated (or always parent, refusing otherwise) is a one-line change.

## Not done here (WP-1 is the data layer only)

No surface, no filter, no chip, no alert, no ordering key, no cohort. Nothing in
this work package changes what the Explosive Growth board selects or how it is
sorted.
