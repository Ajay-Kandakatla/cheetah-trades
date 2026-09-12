# Breakout board — ranked by income and growth, quarter over quarter

**Asked 2026-09-12**, reversing the stage gate from three hours earlier.
Ajay: *"May show any stage but prioritize income and growth only quarter over
quarter"*.

Two changes:

1. **The stage gate is off.** Every stage shows. It is one tap away (`✓ S2 only`,
   `?stages=true`) and the rule it encodes is unchanged.
2. **The order is income + growth, quarter over quarter**, computed over every
   candidate **before** the top-250 cut.

---

## What "quarter over quarter" means here

The board already printed two quarterly numbers and **both were year-over-year**
— the latest quarter against the *same quarter a year earlier*
(`canslim._compute_q_eps_growth`, Q0 vs Q4). This adds the literal reading: **Q0
against Q1**, the quarter that just ended against the one before it
(`backend/sepa/qoq.py`).

They are different orderings, not two names for one number. Measured on his own
board: **Spearman 0.58 revenue, 0.37 EPS**.

| | year-over-year | sequential | own seasonal norm | verdict |
|---|---|---|---|---|
| NFE revenue | +3.6% | **+37.7%** | −3.1% | **sequential is right** — YoY says "flat" and is wrong; adjusted surprise +40.8% |
| MU revenue | +345.7% *(stale, off the 2025 trough)* | **+73.7%** | +15.5% | **sequential is right** — adjusted +58.2% |
| JFB revenue | +417.8% | −89.5% | −95.6% | **sequential is the artifact** — −89.5% is what its Q2 always does; adjusted **+6.2%** |
| FTDR revenue | — | +43.0% | +42.5% | **pure calendar** — adjusted **+0.5%**, η² 0.99 |
| GOLD revenue | *no number* | +59.8% | *no prior year* | sequential answers where YoY cannot |

> **A correction to my own first draft.** I shipped JFB as the headline case for
> sequential catching a collapse YoY hid. Measuring the name's own seasonal
> history reversed it: −89.5% *is* JFB's normal Q2, and YoY was the one telling
> the truth. That reversal is the entire argument for the seasonal reference
> below — made by the example that was meant to argue against it.

Sequential needs **two** quarters where YoY needs five, so it covers more names.

Both are on every row: the sequential number is the headline, the year-over-year
is the small grey line beneath it.

---

## The three things that had to be got right

### 1. A non-material base — and the tiny *positive* one is the real trap

`(Q0 − Q1) / Q1` is meaningless when Q1 is near zero. The obvious case is a
**negative** base: 73 of 250 rows. The case that actually dominated is a tiny
**positive** one, which a "require a positive base" rule does not touch —
another 19 rows, 13 of them under $0.05.

Ranked on the raw percentage, **11 of the top 20 were bought by a base under
$0.10 a share, and 9 of those were tiny-positive**:

```
CDNA +4,040%  $0.05 → $2.07      SNPS +3,056%  $0.09 → $2.84
DBRG +3,733%  $0.03 → $1.15      TXNM +2,033%  $0.03 → $0.64
MRVL   +725%  $0.04 → $0.33      CNH  +1,000%  $0.01 → $0.11
```

Not one is a grower. CNH's eight quarters run **$0.34 → $0.11** — a two-thirds
decline ranked fifth-best on the board. SNPS's $0.09 was a single amortisation
quarter. MRVL is an AI-sector name, so his standing "AI winners on top" tiebreak
would have carried that fake number to the very top.

**`MIN_EPS_BASE = $0.10`.** Below it there is no percentage at all — the cell
reads `loss`, `≈0` or `—` depending on *which* refusal it was, and the row is
never ranked on an invented number. A first profitable quarter after a loss is
still surfaced (`↗`) as an event, not as a growth rate.

### 2. Seasonality — Minervini's objection, measured, and he is right

`scripts/qoq_seasonality.py`. Pooled over all history, each name's own median
subtracted first so scale cannot masquerade as season, with a rotation placebo:

| metric | spread across fiscal quarters | placebo | p |
|---|---|---|---|
| revenue **sequential** | **8.8 pp** | 2.1 pp | **0.0005** |
| EPS **sequential** | **28.2 pp** | 6.5 pp | **0.0005** |
| revenue YoY *(control)* | 0.3 pp | 0.1 pp | 0.106 |
| revenue TTM-sequential | 0.2 pp | 0.1 pp | 0.008 *(nil in size)* |

Reproduced on an independent 250-name draw 40 minutes earlier (the board drifts
intraday): revenue sequential 5.7 pp vs a 1.2 pp placebo, p=0.0005; YoY 0.4 pp,
p=0.085. Dropping every |value| > 150%: 8.7 pp vs 2.1 pp, still p=0.0005 — not
driven by blow-ups.

Within a single name's own series, fiscal quarter explains a median **41.2%** of
the variance of its sequential revenue (phase-shift null 24.3%; **46%** of names
beat their own 95th-percentile null against a 5% chance). For YoY: 3.0% against
a 5.4% null, 4% of names — **exactly chance**. Quarter-vs-same-quarter-prior-year
is built to cancel this, and on his own universe it does.

And it is roughly half the ranking: **48.1%** of the variance in the raw
sequential ordering is the names' own seasonal norms.

**The harm is live right now:** 81% of the board's latest filing is fiscal Q2 —
the seasonally strongest quarter (+3.7 pp revenue, +16.5 pp EPS). Ranking on raw
sequential hands that whole majority a shared upward bias and docks the ~19% on
a different fiscal phase by −5.0 pp revenue / −11.7 pp EPS of pure calendar.

> ZYME: **+90.6%** sequential — and its own Q2 history is **+85.8%**. Genuine
> surprise: **+4.8%**. Its year-over-year was **−90.6%**.

**So the ranking compares each name's sequential move to what the same fiscal
transition did in prior years, and ranks on the difference.** Still quarter over
quarter — measured against the company's own calendar instead of against zero.
The quarterly fetch widened from 8 to 12 quarters so that norm is an *average of
two* prior observations rather than a bet on one year not having been strange
(`SEASONAL_SLOTS = ((4,5), (8,9))`). The scored screens — `sales.score`,
`earnings_quality` — still receive exactly 8 (`canslim._head8`), because moving
a book-cited threshold's input as a side effect of an unrelated feature is how a
methodology drifts without anyone deciding to change it.

**🔁** marks a row making a move it makes every year. The displayed number stays
the plain sequential one; `rank_basis` records which reading the row was ranked
on. Effect on his board: Spearman raw-vs-adjusted **0.789**, 43% of names move
≥19 slots, top-20 overlap 17/20.

### 3. Outliers

One +5,000% print must not own rank 1 on a board of 250. Both legs are blended
by **percentile within the whole candidate list**, so being largest is worth
exactly one rank. Measured: the percentile blend puts SNPS (Stage 4) at **#35**;
a naive raw average puts it at **#3**.

---

## The ordering

```
build rows → AI-sector tag → explosive tag → [optional stage gate]
           → FUNDAMENTALS + QoQ over ALL 2,840 candidates
           → percentile blend → sort → rows[:top] → beta
```

The fundamentals read **moved before the cut**, and that is the change that
matters. It used to run after `rows[:top]`, so ranking on it would have been a
growth-ranked view *of a recency-ranked sample*. The cost is one projected Mongo
query widened from 250 names to 2,840. Beta stays after the cut — it loads
prices.

Sort key, in order: **has an income leg** → the blend → AI-sector rank →
recency → count → symbol. Unknown sorts last at every level; `qoq_score` of
`None` is never a zero.

The income block is deliberate: you cannot prioritise income by ignoring whether
there is any.

---

## Plumbing that had to exist first

The raw quarterly series were **fetched and thrown away** — `_from_hybrid`
consumed them into `sales.compute`/`earnings_quality.compute` and returned
nothing, so **0 of 250** board rows had one.

- `canslim` now persists `rev_q_series` / `eps_q_series` / `ni_q_series` on all
  three source paths. The yfinance path returned `None` for these, which made
  **746 of 3,738 cached names (20%)** a permanent blind spot the Sunday refresh
  could never fill; it now reads the same rows its growth numbers already came
  from.
- `research.DECISION_FIELDS` carries them in the same single projected query.
- `sepa.qoq backfill` fills existing cached documents without rebuilding
  research, and **never touches `cached_at`** — bumping it would extend the life
  of stale fundamentals. Wired into cron at **04:40 daily**, `--limit 900`.
  Coverage went **5.6% → 69.0%** on the first full run.

---

## The honest limit

`scripts/qoq_negative_base.py`. Rank the board on last quarter's **raw**
sequential EPS and look at what those names did the following quarter:

| | median | still positive |
|---|---|---|
| the leaderboard | **+0.4%** | 50% *[25, 70]* |
| **placebo** — everyone else on the board | **+24.0%** | 70% *[61, 79]* |

**The raw sequential leaderboard did worse than the rest of the board.** Part of
that is mechanical — a big quarter becomes the next quarter's denominator — but
that mechanism *is* the finding: a large sequential number is a statement about
one quarter's level, not a property of the business. It is the reason the
ranking uses the seasonally referenced number rather than the raw one.

Two more things this does not claim:

- **Nothing here has been measured against forward stock returns.** This orders
  what already broke out. It does not predict.
- **Fundamentals lag price.** Median quarter-end lag on the board is **74 days**;
  83% of rows are more than 70 days stale. With every stage showing, a name
  already in decline can rank high on a quarter that closed two and a half
  months before the breakdown. The Stage column and the verdict are on the row
  for that reason — measured: of the 72 S3/S4 names on the board, **zero** are
  `is_buyable`.
- **Array position is not quarter adjacency — fixed.** Massive omits a missing
  quarter rather than leaving a placeholder (ORCL is missing Q2 FY2025 *and* Q2
  FY2026; NVDA is missing Q1 FY2025). Measured: **3.2%** of sequential pairs are
  not adjacent, against **12.6%** of the YoY pairs the board has printed for
  months — ASO's compares 2027Q2 against 2025Q4. `q_period_series` now carries
  `fiscal_year*4 + (quarter-1)` beside every series, a non-adjacent pair is
  refused (`gap`) instead of mislabelled, and a seasonal slot that is not a
  whole number of years back is skipped. A legacy document with no period keys
  is still computed — refusing them would blank the ranking rather than improve
  it — and `periods_checked` records that it was not verified. **The
  year-over-year columns are NOT yet period-checked; that is still open.**

---

## Tests

`tests/test_qoq.py` (34) · `tests/test_breakout_qoq_rank.py` (15) ·
`tests/test_log_redaction.py` (+6) · `Breakouts.test.tsx` (+11).
Mutation-tested 2026-09-12 — all eight caught: base floor back to $0.01, zero
base allowed, raw values instead of percentiles, unknown scoring 0, seasonal
reference reading the adjacent transition, echo ignoring sign, income block
removed, unknown not sunk.

## Scripts

All read-only, all must run **inside the api container** (the only place the
Massive key lives; a throwaway container falls back to Yahoo and produces false
negatives):

```
scripts/qoq_vs_yoy.py             sequential vs year-over-year, coverage + agreement
scripts/qoq_negative_base.py      the base problem + the persistence placebo
scripts/qoq_seasonality.py        the seasonality decomposition + mitigations
scripts/qoq_board_composition.py  what the board becomes with the gate off
```
