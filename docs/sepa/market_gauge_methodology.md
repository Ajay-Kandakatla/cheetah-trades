# Market Gauge — methodology

**Code:** `backend/sepa/market_gauge.py` (`compute()` / `get_gauge()`)
**Endpoint:** `GET /market/gauge`
**Page:** `frontend/src/pages/MarketGauge.tsx` (`/market-gauge`) + nav badge `MarketGaugeBadge.tsx` (top-right, every page)
**Contracts:** `backend/tests/test_market_gauge.py` (behavioral) · `tests/test_sepa_contracts.py::test_market_gauge_locked` (source guard)
**Book:** Mark Minervini, *Trade Like a Stock Market Wizard* (2013) — **pp. 79, 248, 303–305; Ch. 5, 12–13**. (Printed page = repo-PDF page − 15.)

---

## 0. What this is — and isn't

A single **0–100 read of the GENERAL MARKET's health**, with a Constructive /
Caution / Risk-Off state and a Minervini exposure band. It is **our own** model.
It is **not** a clone of any paid third-party "market regime" indicator — those
formulas are proprietary and undisclosed, and per Rule #1 we will not
reverse-engineer a real-money signal from a competitor's marketing page.

It is **educational and reactive**, not predictive. Nobody reliably forecasts a
week ahead; this reads the *current* regime so the user reacts on probabilities.
It is **not** personalized buy/sell or position-sizing advice.

## 1. Why a market read at all (book)

- **O'Neil's CANSLIM "M":** ~3 of 4 stocks follow the general market.
- **Minervini Ch. 5 (p.79):** trade *with* the trend; the index Trend Template
  (SPY/QQQ above a rising 50/150/200 stack) tells you if the market is "in gear."
- **Minervini Ch. 12–13 (pp.303–305):** in a correction/bear, "even good
  selection criteria can show poor results … it's not time to buy; it's time to
  sell." **Scale exposure down** in weak tapes, **pyramid up** when the plan
  works, and **pace** re-entry after a correction (p.305).
- **Follow-through (p.248):** wait for a move to "pause and then follow through"
  before committing — confirmation, not a guess.

## 2. Components & weights (sum = 100)

| # | Component | Source | Max pts | Basis |
|---|---|---|---|---|
| 1 | **Index trend** (SPY+QQQ "in gear") | `market_context.market_state()` | 40 | Minervini Trend Template **p.79**, Ch.5 |
| 2 | **Macro regime** | `macro_risk.get_market()` | 20 | our macro-risk model |
| 3 | **Breadth** (% of scan red) | latest scan | 15 | participation |
| 4 | **Index distribution days** | SPY/QQQ price | 15 | **configured** (O'Neil-style) |
| 5 | **Follow-through** | SPY/QQQ price | 10 | concept Minervini **p.248**; trigger **configured** |

State cutoffs: **≥67 Constructive · 34–66 Caution · <34 Risk-Off.**

Exposure bands (educational, Minervini pp.304–305): Constructive 75–100% ·
Caution 25–50% · Risk-Off 0–25%. These restate Minervini's *framework*, not a
recommendation for any individual.

## 3. Configured thresholds — NOT from a book we hold

The distribution-day and follow-through **numeric** rules are O'Neil's domain.
We do **not** have *How to Make Money in Stocks* in the repo, so these are
**configured defaults** — clearly labelled, locked by a source-guard test, and
**not** presented as verified O'Neil page cites. Drop the O'Neil PDF in the repo
and we'll lock them to his exact rules (FTD day-window, distribution-cluster
count, etc.).

| Constant | Value | Meaning |
|---|---|---|
| `DIST_LOOKBACK` | 25 | sessions (~5 weeks) for the distribution count |
| `DIST_DOWN_PCT` | −0.2 | a down close this size on higher volume = a distribution day |
| `DIST_TOPPING` | 5 | ≥ this many = market under distribution |
| `FTD_LOOKBACK` | 12 | sessions to look back for a follow-through day |
| `FTD_UP_PCT` | 1.4 | an up close this size on higher volume = follow-through |

The **definition** of a distribution day (a higher-volume down session) and a
follow-through day (a higher-volume up session confirming a rally) are standard
technical definitions; only the exact **magnitudes/counts** are configured.

## 4. Data flow

`compute()` reuses cached inputs — the SPY/QQQ frames (`prices.load_prices`, the
trend template runs in `market_context`), the cached `macro_risk` regime, and
the latest scan's breadth — then adds the index distribution/follow-through read.
`get_gauge()` wraps it in a 5-minute per-process cache because the top-right
badge hits it on every page. No new cron: the macro-risk hourly cron + the
post-close scan keep the inputs fresh.

`backend/sepa/scanner.py` and the daily scan are untouched (Rule #2).

## 5. Not advice

This page is an educational market-health read. A pattern that worked before
does not guarantee future results; nothing here is a personalized
buy/sell/position-sizing recommendation.
