# Market Gauge — methodology

**Code:** `backend/sepa/market_gauge.py` (`compute()` / `compute_weekly()` / `get_gauge()` / `run_and_persist()`)
**Endpoint:** `GET /market/gauge`
**Page:** `frontend/src/pages/MarketGauge.tsx` (`/market-gauge`) + nav badge `MarketGaugeBadge.tsx` (top-right, every page; shows daily + weekly + pre-open stamp)
**Cron:** `sepa.cli market-gauge-preopen` — Mon–Fri **8:32am ET** (`backend/crontab`); recomputes pre-open with the pre-market gap and persists it for the badge.
**Contracts:** `backend/tests/test_market_gauge.py` (behavioral, incl. weekly + outlook) · `tests/test_sepa_contracts.py::test_market_gauge_locked` + `::test_weekly_gauge_locked` (source guards)
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

## 4b. Multi-horizon: weekly gauge + next-day outlook (2026-06-06)

The gauge now reads **two horizons** and frames the day ahead. None of it predicts
price — it reads the *current* regime across timeframes and names the triggers
that would change it.

### Weekly gauge — `compute_weekly()`

The **same Minervini concepts on WEEKLY bars** ("what kind of *week* are we in").
SPY/QQQ daily frames are resampled to weekly (`df.resample("W-FRI")`) and the
structural reads recomputed. Weekly weights sum to **100** independently of the
daily set (stored in `config.weekly_weights`); same state cutoffs.

| Weekly pillar | wt | What | Book grounding |
|---|---|---|---|
| Weekly trend template | 45 | fraction of 5 Trend-Template gates on weekly MAs | **Minervini p.79 — the book gives the weekly equivalents in parentheses verbatim:** 50-day **(10-week)**, 150-day **(30-week)**, 200-day **(40-week)**. Gates: close>10wk (crit 5), close>30wk & >40wk (crit 1), 10wk>30wk (crit 4), 40wk MA rising ≥1 month (crit 3). |
| Weekly distribution | 20 | distribution *weeks* (down-week on higher weekly volume) in the trailing 8 | concept p.248 / O'Neil-style; **configured** weekly magnitudes |
| Weekly momentum | 15 | index distance from the 30-week MA | **configured** |
| Weekly follow-through | 10 | a +2.5% up-*week* on higher volume, above the 10-week MA | concept **p.248**; **configured** weekly trigger |
| Macro backdrop | 10 | `macro_risk` regime (reused) | `macro_risk` |

The **weekly-MA lengths are NOT a guess — they are Minervini's own parenthetical
weekly equivalents on p.79.** Only the weekly *lookbacks/magnitudes* (8-week
distribution window, 4-week topping count, +2.5% weekly FTD, ±8% momentum band)
are **CONFIGURED** (no book prescribes weekly numbers in the repo) — labelled and
locked by `test_weekly_gauge_locked`.

**Why two horizons:** the daily↔weekly *divergence* is the most useful read. Daily
Caution inside a Constructive weekly structure = a pullback within a larger uptrend
(often a place to buy, not a top); the reverse = treat daily strength as
counter-trend until the week confirms.

### Next-day outlook — `_outlook()`

**Conditions-based, NOT a price prediction.** It restates the daily state's
exposure-band guidance (book **pp.304–305**) as a one-line `label`, a `note`
pairing the daily and weekly reads, and a `watch` list of **leading signals +
regime-flip triggers**: distance to the 67/34 cutoffs ("X pts would flip it up to
Constructive"), distribution approaching the topping count, an absent
follow-through (what up-day would confirm a turn), VIX percentile, the daily↔weekly
divergence, and the pre-market gap. The `note` carries the literal phrase *"not a
prediction of where price closes"*, locked by a contract.

### Implied open — SPY/QQQ ETF pre-market, **NOT** futures

There is **no index-futures feed** in the app (Massive carries the cash ETFs, not
/ES, /NQ — verified). "Implied open" therefore uses the **SPY/QQQ ETF pre-market
print** vs prior close (`prices.bulk_snapshot`), freshness-guarded (last trade
within ~18 h), and is **labelled as the ETF print, not futures.** Unavailable →
`implied_open.gaps = null` + a "not wired" source string — flagged, never faked.
Only the pre-open cron makes this live call (`include_premarket=True`); the
per-page badge path never does. Index futures are listed in `config.not_wired`.

### Pre-open cron + persistence

`sepa.cli market-gauge-preopen` runs **Mon–Fri 8:32am ET** (`backend/crontab`; the
`cron` container's TZ is `America/New_York`). It calls `run_and_persist()` →
`compute(include_premarket=True)` and upserts to Mongo `market_gauge`
(`_id:"latest"`, `computed_at`). `get_gauge()` then **prefers that fresh pre-open
doc (< 20 h old)** so the nav badge shows the morning pre-open read all day
(stamped `pre-open HH:MM ET`); `?force=true` recomputes live. `scanner.py` and the
daily scan are untouched (Rule #2); the only new infra is the cron line.

## 5. Not advice

This page is an educational market-health read across horizons. It reads the
current regime and the triggers that would change it — it does **not** forecast
where price closes today, this week, or any horizon. A pattern that worked before
does not guarantee future results; nothing here is a personalized
buy/sell/position-sizing recommendation.

---

## 2026-06-13 — Gauge trend history

The pre-open persist (`run_and_persist`) only ever wrote a single `_id:"latest"`
doc in `market_gauge` — overwritten every run, so **no series was kept** (you
couldn't see "last Friday was 53"). Added a dated history so the Market Gauge
page can chart the trend:

- **`market_gauge_history` collection** — one doc per ET day (`_id = YYYY-MM-DD`),
  idempotent (the latest read of the day wins). Written by `_record_history()`,
  called from both `run_and_persist()` (the 8:30am cron) and `get_gauge()` on a
  live recompute, so the series builds from normal usage.
- **`GET /market/gauge/history?days=90`** → `{rows: [{date_et, score, state,
  source, computed_at}], available}`, oldest→newest.
- **`<GaugeTrend>`** on the Market Gauge page — an SVG line chart of the score
  with the band backgrounds (≥67 Constructive / 34–66 Caution / <34 Risk-Off).
  Shows a "building history" note until ≥2 points exist.

**History starts 2026-06-13.** Earlier reads were overwritten and can't be
back-filled (the gauge uses live breadth/snapshot inputs that aren't stored
historically), so the line is short at first and grows one point per trading day.
Tests: `tests/test_gauge_history.py` (idempotent-per-day, sorted, soft-fail).
