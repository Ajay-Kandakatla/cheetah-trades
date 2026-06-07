# Market Gauge — methodology

**Code:** `backend/sepa/market_gauge.py` (`compute()` / `get_gauge()`)
**Endpoint:** `GET /market/gauge`
**Page:** `frontend/src/pages/MarketGauge.tsx` (`/market-gauge`) + nav badge `MarketGaugeBadge.tsx` (top-right, every page)
**Contracts:** `backend/tests/test_market_gauge.py` (behavioral) · `tests/test_sepa_contracts.py::test_market_gauge_locked` (source guard)
**Book:** Mark Minervini, *Trade Like a Stock Market Wizard* (2013) — **pp. 79, 248, 303–305; Ch. 5, 12–13**. (Printed page = repo-PDF page − 15.)
**Economic data:** St. Louis Fed **FRED** API (<https://fred.stlouisfed.org/docs/api/fred/>) — series `CPIAUCSL`, `UNRATE`, `FEDFUNDS`, `T10Y3M`, cited inline. FRED supplies the *data*; the scoring thresholds are **CONFIGURED / standard-macro**, NOT book-derived (see the Economic block below).

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

## 2. Pillars & weights (sum = 100)

Thirteen pillars across the six categories Ajay asked for (2026-06-05; the
Economic block was wired to FRED and weighted **HEAVY** on 2026-06-06). Each is
REAL data or honestly degraded to neutral — **nothing is fabricated.**

| Category | Pillar | wt | Source | Basis |
|---|---|---|---|---|
| Quant | Index trend "in gear" | 15 | `market_context.market_state()` | Minervini Trend Template **p.79**, Ch.5 |
| Quant | Volatility (VIX + 252d pct) | 8 | `market_regime._stress_score("^VIX")` | VIX percentile |
| Trend tech | Index distribution days | 6 | SPY/QQQ price | **configured** (O'Neil-style) |
| Trend tech | Follow-through | 4 | SPY/QQQ price | concept Minervini **p.248**; trigger **configured** |
| Breadth | % of scan red | 6 | latest scan | participation |
| Flow & Liquidity | Net $-vol + Chaikin MF | 8 | scan `volume.*` aggregate | accumulation vs distribution |
| Sentiment | Options put/call (median SOIR) | 6 | `soir_latest` aggregate | Schaeffer's OI ratio |
| Alt-data | Insider cluster-buy breadth | 4 | scan `insider.*` (SEC Form 4) | open-market buys |
| Economic | Yield curve 10y−3m | 8 | FRED `T10Y3M` | inversion = recession risk |
| Economic | Inflation (CPI YoY) | 9 | FRED `CPIAUCSL` | **configured** (Fed ~2% target) |
| Economic | Unemployment | 9 | FRED `UNRATE` | **configured** (Sahm-style: rising = recession) |
| Economic | Fed funds rate | 8 | FRED `FEDFUNDS` | **configured** (tightening = headwind) |
| Macro | Regime + news events | 9 | `macro_risk.get_market()` | VIX/distribution/news |

Economic block = **34/100** (yield 8 + CPI 9 + unemployment 9 + Fed-funds 8); the
9 non-economic pillars were trimmed proportionally (×66/89) so the total stays 100.

State cutoffs: **≥67 Constructive · 34–66 Caution · <34 Risk-Off.**

### Economic block (FRED) — REAL data, CONFIGURED scoring

The four Economic pillars read live from the free **St. Louis Fed FRED API** via
`backend/sepa/fred.py`. The **data is real and cited by FRED series id**; the
numbers that turn each series into a 0–1 health score are **CONFIGURED /
standard-macro** — *not* from any book we hold (Minervini times the market off
index price action, not a weighted CPI/jobs/Fed-funds gauge). They are labelled
as such and locked by the source-guard, exactly like the O'Neil-style numbers.

| Pillar | FRED series | Read | Health score (CONFIGURED) |
|---|---|---|---|
| Inflation | `CPIAUCSL` | YoY % | full ≤ 2% (Fed target), 0 at ≥ 6%; lower = less Fed pressure. One-sided — disinflation lifts the score automatically next print. |
| Unemployment | `UNRATE` | level + 6-mo change | 50% level (full ≤ 3.5%, 0 ≥ 7%) + 50% trend (rising +0.5 pp/6 mo → 0, the Sahm-rule recession signal). |
| Fed funds | `FEDFUNDS` | level + 12-mo change | 60% direction (cutting → tailwind, hiking → headwind) + 40% level (≤ 2% accommodative → ≥ 5.5% restrictive). |
| Yield curve | `T10Y3M` | spread (FRED publishes it directly) | inverted (≤ −0.5) → 0, steep (≥ +1.5) → full. Replaces the old yfinance `^TNX`/`^IRX` proxy and its ×10/NaN hack. |

**Why HEAVY (34/100):** Ajay chose to let the macro block outweigh the price-tape
block (2026-06-06). Caveat (also in code): CPI/UNRATE/FEDFUNDS are *lagging,
monthly* series, so the gauge reacts to a **confirmed macro regime, not a turn**.
The CPI leg is one-sided (it does not penalise outright deflation); revisit if the
regime ever flips to a deflation scare.

**Key + cache:** the key is read from `FRED_API_KEY` (env var, never hardcoded;
free at <https://fredaccount.stlouisfed.org/apikeys>). Each series is cached
in-process for 24 h. **No FRED key → the four pillars degrade to neutral and say
so** (`"n/a — set FRED_API_KEY"`), never a fabricated number.

### Feeds we STILL do NOT have (flagged, not faked)

True order-flow / dark-pool tape · a fear/greed index. These stay listed in
`config.not_wired`; their absence degrades nothing to a fake number. Give me an
order-flow provider and I'll wire them as real pillars too.

**Put/call direction:** a heavy put-skew is read as *defensive* (lower health) —
the tape-health reading. Standard contrarian caveat applies (extreme fear can
mark a bottom), so it's weighted modestly (6).

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

The **Economic block's** scoring thresholds (the CPI/UNRATE/FEDFUNDS/T10Y3M
cut-offs in §2) are configured in the same spirit: the FRED *data* is
authoritative and cited by series id, but the macro *interpretation* (Fed ~2%
target, Sahm-rule rising unemployment, tightening-vs-easing, curve inversion) is
standard-macro, **not** book-derived. The same source-guard lock applies.

## 4. Data flow

`compute()` reuses cached inputs — the SPY/QQQ frames (`prices.load_prices`, the
trend template runs in `market_context`), the cached `macro_risk` regime, and
the latest scan's breadth — then adds the index distribution/follow-through read.
`get_gauge()` wraps it in a 5-minute per-process cache because the top-right
badge hits it on every page. The Economic pillars add FRED reads
(`backend/sepa/fred.py`), each cached in-process for 24 h — one HTTP call per
series per day. **No new cron:** the macro-risk hourly cron + the post-close scan
keep the inputs fresh, and the 5-minute gauge cache plus the daily FRED cache
absorb the badge's per-page hits.

`backend/sepa/scanner.py` and the daily scan are untouched (Rule #2). The only
new infra is the `FRED_API_KEY` env var (add it to `backend/.env`).

## 5. Not advice

This page is an educational market-health read. A pattern that worked before
does not guarantee future results; nothing here is a personalized
buy/sell/position-sizing recommendation.
