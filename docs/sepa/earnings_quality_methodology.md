# Earnings-Quality Score — Methodology

**Source:** Mark Minervini, *Trade Like a Stock Market Wizard* (McGraw-Hill, 2013),
**Chapter 8 "Assessing Earnings Quality," book pp. 140–159.** PDF in
`docs/TradeLikeaStockMarketWizard(2013).pdf`.

**Code:** `backend/sepa/earnings_quality.py` · **Tests:**
`backend/tests/test_earnings_quality.py` (behavioral + regression),
`backend/tests/test_sepa_contracts.py` (source-guard).

Every formula below cites the page it derives from. Thresholds marked
**(codification)** are ours — Minervini gives the concept and direction but not an
exact cutoff; those are locked in the contract test so they can't drift silently.

---

## Why this exists

The chapter's thesis (**p.141**): high-quality earnings are **revenue-driven**.
> "Earnings improvement from cost cutting, plant closures, and other so-called
> productivity enhancements walks on short legs… sustainable earnings growth
> requires revenue growth."

Before this, the scanner's only fundamentals input was the O'Neil CANSLIM C/A/I
*levels* (latest-Q EPS ≥25%, 3-yr annual EPS ≥25%, institutional ownership
40–80%). It checked whether EPS was high, never whether the earnings were **good**
— accelerating, margin-backed, sales-driven, and free of balance-sheet warning
signs. This score adds that.

## Inputs (no new API call)

All from the **same** 8-quarter Massive `/vX/reference/financials` fetch
`canslim._fetch_massive_financials` already makes, exposed as newest-first series
(index 0 = latest filed quarter): `eps_q_series`, `rev_q_series`, `ni_q_series`,
`inv_q_series`. Receivables arrive as an optional `recv_q_series` (yfinance
supplement, top-N enrich only — see "Data limits").

`YoY[i] = (series[i] − series[i+4]) / |series[i+4]|` — same-quarter-a-year-ago, the
formula `canslim` and `sepa/sales.py` already use.

## What it computes

| Signal | Rule | Page |
|---|---|---|
| **EPS acceleration** | YoY EPS growth rate rising across quarters (`eps_g[0] > eps_g[1] > eps_g[2]`) | p.140, 158 |
| **Sales acceleration** | reuses `sepa/sales.py` (Bonde-anchored YoY rev accel + consecutive growth) | p.140, 158 |
| **Margin expansion** | net-profit-margin = `net_income / revenue`; YoY expansion + sequential 3-q rise | p.145–147 |
| **The Code 33** | EPS, sales, **and** net margin all rising for **3 consecutive quarters** | p.158–159 |
| **Sales-driven quality** | penalize EPS ≥25% on <5% sales with no margin expansion (cost-cut/one-time beat) | p.141–144 |
| **Inventory red flag** | inventory YoY > sales YoY by ≥15 pp **and** sales not strong | p.153–156 |
| **Receivables / double trouble** | receivables YoY > sales YoY; both = "double trouble" (yfinance) | p.156–157 |
| **Surprise (light)** | small bonus from `last_earnings_surprise_pct` (wired at the scanner) | p.140, 147–151 |

### The Code 33 (p.158–159) — the chapter's headline rule
> "Look for what I call a Code 33 situation, three quarters of acceleration in
> earnings, sales, and profit margins."

`code_33 = True` iff, newest-first: `eps_YoY[0] > eps_YoY[1] > eps_YoY[2] > 0`
**and** `rev_YoY[0] > rev_YoY[1] > rev_YoY[2] > 0` **and** `npm[0] > npm[1] > npm[2]`.
(Fig 8.10 reads most-recent-quarter-first, so "rising" means the latest is largest.)
It's deliberately strict and therefore **rare** — that's the point.

### Inventory red flag + the bullish-build exception (p.155–156)
Inventory growing much faster than sales can mean "weakening sales, misjudgment of
future demand, or both" (p.155). **But** (p.156) inventory/raw-material build
*ahead of* strong, accelerating demand is bullish, not piling up. So the flag is
**suppressed when sales YoY ≥ 25%** *(codification)* — e.g. a chipmaker building
inventory into +85% revenue is not flagged.

## Scoring (0–100)

Additive, then clamped. Positive contributions reward sales-backed, accelerating,
margin-expanding earnings; penalties dock low-quality beats and red flags:

```
+ eps_level   (0–20)   latest EPS YoY, full at ≥25% (p.140)
+ sales       (0–20)   sepa/sales.py score /100 (p.140,158)
+ margin      (0–15)   net-margin YoY expanding=15 / flat=7 / contracting=0 (p.145-147)
+ eps_accel   (0–12)   3-q rise=12, 2-q=6 (p.158)
+ rev_accel   (0–12)   3-q rise=12, else sales-accel=6 (p.158)
+ margin_accel(0–11)   net margin rising 3 sequential quarters (p.158)
+ surprise    (0–10)   beat magnitude (wired at scanner) (p.147-151)
− low_quality (25)     EPS jump on flat sales, no margin expansion (p.143)
− inventory   (10/20)  inventory (10) / double-trouble (20) red flag (p.155-157)
```

`code_33` is the conjunction of the three 3-q acceleration legs (so a true Code 33
already earns the full 35 acceleration points). Output also carries a `tier`
(`code33` / `accelerating` / `steady` / `red_flag` / `weak`) and a page-cited
`reason` string for the card chip.

## Data limits (Rule #1 — we do NOT invent precision)

Verified live against Massive `/vX/reference/financials` on 2026-06-08:

- ✅ income statement: `revenues`, `diluted_earnings_per_share`,
  **`net_income_loss`**, `gross_profit`, `operating_income_loss`.
- ✅ balance sheet: **total `inventory`**.
- ❌ **No `accounts_receivable`** on Massive → the receivables / "double trouble"
  half (p.156–157) needs a **yfinance** `quarterly_balance_sheet` supplement, run
  only on the top-N enrich set. Absent, the receivables flag is `None` (never
  silently treated as "clean").
- ❌ **No finished-goods / WIP / raw-materials split** exists in either provider —
  it lives only in 10-Q footnotes. Minervini's **Fig 8.9 finished-goods-specific**
  red flag is therefore **out of scope**; we compare *total* inventory vs sales,
  which captures the aggregate "piling up" signal but not the sub-breakdown.

## Not implemented (stated, not silently dropped)

- Stripping nonrecurring/one-time items line-by-line (p.141–143) — standardized
  statements don't reliably isolate them; we use the sales-backed proxy instead.
- "Lowered-then-beat" estimate-revision detection (p.142) — needs an estimate
  history feed we don't store.
- Price reaction / post-earnings drift (p.147–149) — already lives in
  `backend/setups/post_earnings_drift.py`; not duplicated here.
- Universe-wide pre-cut gating — earnings quality re-scores the **top-N enrich
  set** (like CANSLIM today), not every name pre-ranking (perf).
