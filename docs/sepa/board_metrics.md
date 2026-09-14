# CPA columns — Explosive Growth + Breakouts

Ajay 2026-09-13: *"In the explosive growth and breakout can you add few more
columns to the table … 3. Debt … Or any other value added metrics to check
company valuation. Think like a CPA analyst and stock valuation."*

Four numeric columns on both boards. Measured coverage on the live boards the
day they shipped:

| Column | Growth (29) | Breakouts (250) |
|---|---|---|
| **Shares YoY** (dilution) | 86% | 91% |
| **Cash − Debt** | 100% | 99% |
| **EV/Sales** | 100% | 99% |
| **FCF yield** | 90% | 89% |

The bar is the repo's own, written at `sepa/research.py:154`: *"a column blank
for a third of the board is worse than no column"* — which is why `moat` (64.7%)
was kept off the Hottest Sectors table. All four clear it.

---

## 1. What the dilution column immediately showed

**The two boards are opposites.**

- Explosive Growth: median **+11.8%** share growth, 16 of 25 diluting more than
  5%, only **2** buying back.
- Breakouts: median **−0.2%**, **119 of 228** buying back.

The +100%/+100% screen is selecting companies funding their growth with stock,
and nothing on that board said so before this column. SM **+109%**, DX **+98%**,
HNI **+53%**, PROP **+321%** — against NVDA **−1.0%** and TER **−1.5%**.

---

## 2. Why a board-scoped cache, not the weekly research cache

The app already had one debt number — `moat.components.capital.net_debt_ebitda`
— and it is **blank for 60% of both boards** (99/250 breakout, 11/29 growth).

That is not missing data, it is a refresh-time fetch failure: the weekly research
cron walks 3,738 symbols at 6 workers and gets rate-limited. Fetched for the ~275
names that actually appear on the two boards, the same provider answers **98.8%**.

So `sepa/board_metrics.py` caches per-**board** (Mongo `board_metrics`, 36h TTL),
warmed by a cron at 17:45 ET on market days — after the 16:30 fast scan and after
the 17:20 turning-bullish sweep, so they never contend for the same provider.

**Two sources, split by what each can actually answer:**

- **Massive** `/vX/reference/financials` → `income_statement.diluted_average_shares`.
  The only source with share-count *history*, which dilution needs. Its balance
  sheet is useless here — measured `cash` at 1.2-3.4%, `long_term_debt` at 27.6-39.6%.
- **yfinance `.info`** → `totalCash`, `totalDebt`, `enterpriseToRevenue`,
  `freeCashflow`, `marketCap`, `sector`. 98-100% on board-sized lists.

---

## 3. Two defects caught before shipping

### 3.1 The derived-Q4 trap

**23.8% of the provider's quarterly rows are derived Q4s** — annual minus the
three reported quarters — carrying `filing_date: None`. For a flow item that
subtraction is fine. For an **average share count** it is nonsense:

```
NVDA  Q4 FY2026  filed=None  diluted_average_shares =    -28,000,000
MU    Q4 FY2025  filed=None  diluted_average_shares =      2,000,000   (real ~1,140,000,000)
SM    Q4 FY2025  filed=None  diluted_average_shares =         10,000   (real ~115,000,000)
SM    Q4 FY2024  filed=None  diluted_average_shares =       -168,000
```

The tempting guard is *"drop anything implausibly small"*. **That guard is
wrong**, and MU is the proof: 2,000,000 is a perfectly ordinary share count for
a real microcap, so a magnitude floor passes MU's garbage *and* rejects genuine
small names. `filing_date is None` separates derived from reported exactly, with
no invented number, so that is the whole test. Pinned by
`test_NEGATIVE_the_guard_is_the_filing_date_NOT_a_magnitude_floor`.

### 3.2 The RKT basis flip

Rocket Companies measured **+1,559% dilution**. It is not diluting. Its reported
diluted-share series *oscillates*:

```
Q2 2026  2,843,538,118      Q1 2026  2,846,974,742
Q3 2025  2,106,227,188      Q2 2025    171,438,105   <-- 12x lower
Q1 2025  2,001,936,379      Q3 2024  2,003,296,515
Q2 2024    139,647,845      Q1 2024  1,991,982,680
```

Rocket runs an **up-C structure**: in quarters where the Class D units are
*anti-dilutive* they drop out of the EPS denominator entirely, so a Q2-vs-Q2
comparison silently measures a near-basic denominator against a fully-diluted
one. The arithmetic is perfect and the number is meaningless.

`SPLIT_SUSPECT_RATIO` did **not** catch it — live shares 980,550,267 over
2,843,538,118 is 0.345 against a 0.333 floor. It missed by a hair, which is
exactly how much to trust a single cross-check.

The general bug is a denominator whose **basis changes between quarters**.
Genuine dilution is smooth: even SM, the most diluted real name at +109% YoY,
never moves more than 1.73× between adjacent quarters. A basis flip moves 12×.
So `BASIS_FLIP_RATIO = 4.0` blanks the cell with `reason: unstable_share_basis`.

Both `SPLIT_SUSPECT_RATIO` and `BASIS_FLIP_RATIO` are **loose sanity bounds, not
measured thresholds**. They are set where a real capital raise cannot reach them,
and their failure mode is a blank cell, never a wrong number. PROP's genuine
+321% (a smooth 16.7M → 185.6M ramp) survives both.

---

## 4. Sector honesty

A bank's deposits are liabilities; a mortgage REIT is levered by design and has
no meaningful revenue line — **ARR measures EV/Sales at 41× and NLY at 44×**, and
neither reports free cash flow. Rendering those as ordinary numbers invites
exactly the wrong comparison against a software name at 12×.

`NON_OPERATING_SECTORS = ("Financial Services", "Real Estate")` → the cell reads
**n/a** with a tooltip saying why. Measured share of the boards: growth 6/29
(20.7%), breakout 45/250 (18%).

---

## 5. What a blank means

Every refusal is named, and the tooltip says which one it was — a blank with no
explanation reads as a bug, a blank that names the refusal is a fact about the
filing.

| `shares_yoy_reason` | Meaning |
|---|---|
| `no_year_ago_quarter` | No reported quarter exactly one year earlier. **Not** estimated from a nearer quarter — that reports a different number of quarters as a year of dilution. |
| `split_suspected` | The filing's share count is >3× from today's shares outstanding; a split or recapitalisation sits between them. |
| `unstable_share_basis` | The RKT case above. |

A row the cache cannot answer for keeps **no** metric keys at all, so the
frontend renders an em-dash rather than a zero — the same discipline
`research.decision_snapshot` uses.

---

## 6. Sort behaviour

- **EV/Sales opens ascending** — it is a price tag, and the reason to open it is
  to find what is cheap for its growth (the same axis the Under Value tab's PSG
  screen reads).
- **Dilution opens descending** — it is a risk column, and the row worth seeing
  is the heaviest issuer.
- A refused value sorts as **unknown**, sinking in *both* directions. A figure
  the app declined to compute must never outrank a measured one.

On Breakouts the metrics attach **after** the top-N cut, like `beta` — they are
display fields and decide no ranking, so the documented "rank before the cut"
rule (which binds fields that *do* decide the ranking) does not apply. On
Explosive Growth they attach at **read** time, not build time: that board
rebuilds weekly while these refresh every 36h, so baking them into the stored
doc would freeze a balance sheet to the Sunday the screen last ran.

---

## 7. What was measured and REJECTED

Not shipped, each on a measured basis rather than taste:

| Metric | Why not |
|---|---|
| Net Debt/EBITDA | Meaningless for net-cash small caps (AXTI −23.5, SITM −13.0), blank for every mortgage REIT. Cash − Debt answers it honestly. |
| PEG | 24% growth / 40% breakout coverage. |
| Rule of 40 | Inputs fine, **output is noise** on a +100% screen: PTGX 3824, LQDA 1893, MU 426. Calibrated for 20-40% SaaS growth. Would have passed a coverage check and still been wrong. |
| Piotroski F-Score | 10% / 20% coverage. |
| Cash runway / burn | 0/29 — the provider's `cash` field is 1-3% populated. |
| ROIC vs WACC | WACC is not obtainable from any wired source. |
| Altman Z | Needs retained earnings (not exposed) and would mislabel exactly the financials. |
| Accruals ratio | Duplicative — `sepa/earnings_quality.py` already ships the Minervini Ch.8 red flags. |
| P/E, PEG as "obvious" adds | **The premise was wrong**: only 3/29 (10.3%) of the growth board has negative net margin and trailing P/E is present for 83%, because the screen requires EPS +100%. |

---

## 8. Files

```
backend/sepa/board_metrics.py          the module, the guards, the CLI
backend/sepa/breakout.py               attach after the cut, beside beta
backend/growth/api.py                  attach at read time in _payload
backend/crontab                        45 17 * * 1-5
backend/tests/test_board_metrics.py    12 tests
frontend/src/lib/boardMetrics.ts       formatting + tones, shared by both boards
frontend/src/lib/boardMetrics.test.ts  13 tests
frontend/src/lib/growthSort.ts         4 sort keys + labels + initialDir
frontend/src/components/ExplosiveGrowth.tsx
frontend/src/pages/Breakouts.tsx
frontend/src/hooks/useBreakoutBoard.ts
```
