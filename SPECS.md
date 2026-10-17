# Cheetah Market App — Technical Specs

> Generated 2026-04-24. Source-of-truth files were read directly; the Minervini PDF
> at `backend/sepa/minervini.pdf` was **NOT opened** in this pass — every threshold
> sourced from the book is marked `(UNVERIFIED — needs human check against PDF)`.
> Page references were copied from inline docstrings the original author wrote;
> trust them only after spot-checking.

---

## 1. System Overview

**Purpose.** A personal multi-market research dashboard. Three concerns:

1. **Curated Cheetah Score** — a static, hand-edited universe of US growth stocks
   with a 5-factor composite (growth/momentum/quality/stability/value).
2. **Live Stream** — real-time tick feed (Finnhub WS + REST poller) with
   server-computed RSI(14), VWAP, and sparkline.
3. **SEPA (Minervini) Pipeline** — full screener (Trend Template + RS + Stage +
   Volume + VCP/Power-Play + base count + sell signals + position sizing) plus
   catalyst (news/earnings) and insider (SEC EDGAR) enrichment.
4. **Indian Market** — Yahoo Finance NSE/BSE quotes + Indian-edition Google
   News.

**Tech stack.**
- Backend: Python 3.9+, FastAPI 0.115, uvicorn, httpx, websockets, yfinance,
  pandas (transitive via yfinance/pyarrow), python-dotenv. SSE for streaming.
- Frontend: React 18, Vite 5, TypeScript 5, react-router-dom 6. No state lib,
  no UI lib — plain CSS in `src/styles/*.css`.
- Persistence: MongoDB (`price_cache`, `scan_runs`, `candidate_snapshots`), with
  parquet at `~/.cheetah/prices/` as a fallback when Mongo is down. JSON at
  `~/.cheetah/scans/` for `latest.json` + `brief.json`. In-process dicts for
  tick window + news cache.
- Scheduling: macOS launchd (two plists in `launchd/`).

**Deployment model.** Local-only laptop app. `run-app.sh` boots backend on
`:8000` and Vite dev server on `:5173`. Vite proxies `/cheetah, /stream, ...`
to backend so the SPA is same-origin in dev. No production build is wired into
serving (a `frontend/dist` exists from a manual `npm run build`).

---

## 2. Backend (FastAPI) — `backend/main.py`

| Method | Path | Inputs | Output | Side effects | Calls |
|---|---|---|---|---|---|
| GET | `/health` | — | `{status, cached_symbols[], finnhub_configured, time}` | — | `cache.snapshot` |
| GET | `/snapshot` | `?symbols=A,B,C` | `{<sym>: Quote}` | when `?symbols=` is supplied, missing entries are filled from SEPA's daily-bar cache (yesterday's close, marked `stale: true`) so off-hours / restart UIs aren't blank | `cache.snapshot` + `_quote_from_sepa_cache` |
| GET | `/symbol-search` | `?q=ASM` | `{q, results: [{symbol, display_symbol, name, type}], cached}` | proxies Finnhub `/api/v1/search` with US exchange filter; cached 6h per query in-process | `_symbol_search_cache` |
| GET | `/cheetah` | — | `{weights, stocks[], computedAt}` | — | `cheetah_data.with_computed_scores` (recomputes from `FORMULA_WEIGHTS`) |
| GET | `/competitors` | — | `[{anchor, headline, sub, peers[], anchorStock}]` | — | `cheetah_data.get_competitor_groups` |
| GET | `/unicorns` | — | `Unicorn[]` | — | static `cheetah_data.UNICORNS` |
| GET | `/etfs` | — | `Etf[]` | — | static `cheetah_data.ETFS` |
| GET | `/news` | `?symbol=` (optional) | `{symbol, items[], fetchedAt}` | populates `news._cache` | `news.fetch_news` / `news.market_news` |
| GET | `/stream` | `?symbols=CSV` | SSE stream of `event: quote\ndata: {Quote}` | `subscribe_symbols` (adds to `tracked_symbols`, queues WS subs, fires REST one-shot) | `cache.snapshot` loop |
| GET | `/sepa/scan` | — | latest `scan` payload or `{candidates:[], message}` | reads `~/.cheetah/scans/latest.json` | `sepa.scanner.load_latest` |
| POST | `/sepa/scan` | `?with_catalyst&fast&mode` | full scan payload | `?fast=true` joins cached research with today's prices (~20-30s); default heavy path runs every per-symbol analysis (~3-15min). `?mode` = curated / sp500 / russell1000 / expanded | `sepa.scanner.scan_universe` / `scan_universe_fast` |
| GET | `/sepa/research/status` | — | `{available, total, fresh, stale, oldest_age_sec, newest_age_sec, ttl_sec}` | reports freshness of `sepa_research_cache` | `sepa.research.status` |
| POST | `/sepa/research/refresh` | `?mode&no_canslim&workers` | `{refreshed[], failed[], total, duration_sec}` | heavy weekly batch — refreshes VCP / Power Play / CANSLIM / liquidity / ADR / IPO age / company name across the universe | `sepa.research.refresh_universe` |
| GET | `/sepa/brief` | — | latest `brief.json` | — | `sepa.brief.load_brief` |
| POST | `/sepa/brief` | — | brief payload | writes `~/.cheetah/scans/brief.json`; pulls catalyst+insider for top5+watchlist | `sepa.brief.generate_brief` |
| GET | `/sepa/candidate/{symbol}` | path | `{symbol, base, catalyst, insider, ipo_age, smart_money}` | catalyst pulls news+earnings; insider hits SEC EDGAR; smart_money fans out to Finnhub + RSS + Reddit (15-min Mongo cache) | `catalyst_for, insider_activity, ipo_age, smart_money_for` |
| GET | `/sepa/smartmoney/{symbol}` | path | `{analyst, blogs, reddit, fetched_at, cached}` | 15-min cache in `smart_money_cache` Mongo collection | `sepa.smart_money.smart_money_for` |
| GET | `/sepa/dual-momentum` | `?top_n=15&lookback_days=252&min_rs_rank=0` | `{regime, rows, picks, universe_size, gate_lookback_days}` | reuses latest scan + cached prices; computes 1/3/6/12-month returns + Antonacci two-gate ranking | `sepa.dual_momentum.compute` |
| GET | `/sepa/analysis/{symbol}` | path | `{fundamental, technical, esg, analyst, cached}` | Fidelity-style multi-panel readout. 60-min Mongo cache (`stock_analysis_cache`). Composes yfinance fundamentals, derived technical sentiment, Sustainalytics ESG, Finnhub analyst rating | `sepa.stock_analysis.analysis_for` |
| POST | `/sepa/rescan/{symbol}` | path | analyzed dict for one symbol | force-refreshes parquet cache for symbol | `prices.load_prices(force=True), rs_rank.rs_ranks, scanner._analyze_symbol` |
| POST | `/sepa/analyze/{symbol}` | path, `?with_catalyst=true` | full SEPA analysis dict | works for ANY valid US ticker (not just universe members). Pulls fresh prices, computes RS in latest scan's universe context, runs full Trend/Stage/VCP/Power Play/fundamentals stack. Persists into latest scan + research cache. | on-demand single-ticker analyze |
| GET | `/sepa/watchlist` | — | `[{symbol, entry, stop, shares?, added}]` | reads `watchlist.json` | `scanner.load_watchlist` |
| POST | `/sepa/watchlist` | `?symbol&entry&stop&shares=0` | updated list | writes `watchlist.json` | `scanner.add_to_watchlist` |
| DELETE | `/sepa/watchlist/{symbol}` | path | updated list | writes `watchlist.json` | `scanner.remove_from_watchlist` |
| POST | `/sepa/position-plan` | `?entry&stop&account_size&risk_per_trade_pct=1.0&max_stop_pct=10.0` | `PositionPlan.to_dict()` | — | `sepa.risk.plan_position` |
| POST | `/sepa/notify/test` | — | `{sent: bool}` | sends "Cheetah test ping" via Twilio | `sepa.notify.send_whatsapp` |
| POST | `/sepa/alerts/price` | `?symbol&kind&level&channels=CSV&note=` | created alert doc | inserts into `price_alerts` Mongo collection | `sepa.price_alerts.create` |
| GET | `/sepa/alerts/price` | — | `PriceAlert[]` | reads `price_alerts` | `sepa.price_alerts.list_active` |
| DELETE | `/sepa/alerts/price/{alert_id}` | path | `{ok: bool}` | removes from `price_alerts` | `sepa.price_alerts.delete` |
| GET | `/sepa/alerts/recent` | `?since=<unix>` | `{fires: AlertFire[]}` | reads `price_alert_fires` since ts | `sepa.price_alerts.recent_fires` |
| GET | `/indian-stocks` | — | `{stocks[], indices[], fetchedAt}` | populates `indian_market._quote_cache` | `indian_market.fetch_indian_market` |
| GET | `/indian-news` | `?symbol=` (optional) | `{symbol, items[], fetchedAt}` | populates `news._cache` under `__IN_*__` key | `news.indian_news` |

**Module-level state in `main.py`:**
- `cache: QuoteCache` — `_data` dict + `_ticks` deque per symbol (maxlen=`TICK_WINDOW`=64).
  Each `update()` recomputes RSI(14) + VWAP + last-32 sparkline.
- `tracked_symbols: set[str]`, `_ws_subscribe_queue: asyncio.Queue` — dynamic subs.
- Background tasks (lifespan): `finnhub_ws_consumer` (auto-reconnect, exponential
  backoff capped at 60s), `finnhub_rest_poller` (every `POLL_INTERVAL_SEC`=5s).

**Indicator math (`main.py`):**
- `rsi_wilder(prices, period=14)` — standard Wilder smoothing; returns 100 if
  no losses, None if `<period+1` bars.
- `vwap(prices, volumes)` — `Σ(p·v)/Σv` over current tick window.

**CORS:** allowlist `localhost:5173` and `127.0.0.1:5173`.

---

## 3. SEPA Module — `backend/sepa/*`

> Cache root for everything: `~/.cheetah/`. Subdirs: `prices/` (parquet), `scans/`
> (`latest.json`, `brief.json`, `watchlist.json`).

### `__init__.py`
Docstring only: "Minervini SEPA — screener, morning brief, catalyst + insider signals."

### `prices.py` — daily OHLCV loader with Mongo + parquet cache
- **Public:** `load_prices(symbol, period="2y", force=False) -> Optional[pd.DataFrame]`
  with columns `[open, high, low, close, volume]`, indexed by date.
- **Provider:** selected by `PRICE_PROVIDER` env (`massive` default → falls back
  to `yfinance` on miss/error). Massive endpoint:
  `GET https://api.massive.com/v2/aggs/ticker/{SYM}/range/1/day/{from}/{to}`
  using `MASSIVE_API_KEY`. Free tier is 5 req/min — paid plan recommended for
  full-universe scans.
- **Cache layers, in order:**
  1. **MongoDB** — `cheetah.price_cache` collection, one doc per symbol
     `{symbol, bars: [{date, open, high, low, close, volume}], cached_at}`,
     unique index on `symbol`. Survives container restarts and is shared
     between the api and cron services. TTL = **20 hours** (`CACHE_TTL_SEC`).
  2. **Parquet** — `~/.cheetah/prices/{SYM}.parquet`, used as fallback when
     Mongo is unreachable. Same TTL. Requires `pyarrow`.
- Cache miss (or `force=True`) calls the provider, then writes to **both**
  cache layers. Mongo is backfilled from parquet when only parquet is fresh.

### `universe.py` — scanning universe
- `UNIVERSE` — hardcoded ~250 US tickers (mega-cap tech, semis, software, consumer
  growth, biotech, fintech, energy/industrials, China ADRs, small/mid momentum,
  benchmarks SPY/QQQ/IWM).
- **Public:** `load_universe()` priority: `SEPA_UNIVERSE_FILE` env (text file path)
  → `SEPA_UNIVERSE` env (CSV) → default `UNIVERSE`.
- `BENCHMARK = "SPY"`.

### `trend_template.py` — Minervini Trend Template (8 criteria)
Dataclass `TrendResult(symbol, pass_all, passed, checks, preferred, price, ma50,
ma150, ma200, week52_high, week52_low, pct_above_low, pct_below_high)`.

`evaluate(symbol, df) -> Optional[TrendResult]`. Requires ≥220 bars.

| Check key | Rule |
|---|---|
| `price_above_ma150_and_ma200` | close > MA150 and > MA200 |
| `ma150_above_ma200` | MA150 > MA200 |
| `ma200_trending_up` | MA200 today > MA200 22 bars ago |
| `ma50_above_ma150_above_ma200` | MA50 > MA150 > MA200 |
| `price_above_ma50` | close > MA50 |
| `at_least_30pct_above_52w_low` | `(price/52w_low - 1) ≥ 30%` |
| `within_25pct_of_52w_high` | `(1 - price/52w_high) ≤ 25%` |
| `rs_rank_at_least_70` | set by scanner after RS pass; standalone defaults `True` |
| `preferred.ma200_trending_up_5mo` | MA200 today > MA200 110 bars ago |

### `rs_rank.py` — IBD-style Relative Strength
- `_return(df, lookback_days)` — point-to-point return.
- `rs_score(df)` — weighted: `0.4·r63 + 0.2·r126 + 0.2·r189 + 0.2·r252`.
- `rs_ranks(symbols) -> {sym: 1-99}` — percentile-rank scores via pandas, scaled.

### `stage.py` — 4-stage classifier
`classify(df)` returns `{stage, label, slope_up, dist_200_pct}`:
- **Stage 2 (Advancing)**: slope_up AND price > MA50 > MA150 > MA200.
- **Stage 4 (Decline)**: slope_down AND price < MA50 < MA150 < MA200.
- **Stage 3 (Topping)**: price < MA50, slope still up, price within 10% of MA200.
- **Stage 1 (Basing)**: default.

Slope = MA200 vs MA200[-22].

### `volume.py` — accumulation / distribution
`analyze(df)` returns `{up_down_vol_ratio, accumulation, vol_dryup, is_drying_up,
high_vol_breakout, last_vol, avg_vol_50}`.
- `up_down_vol_ratio` = sum(vol on up days) / sum(vol on down days) over last 50.
- `accumulation` = ratio ≥ 1.0.
- `vol_dryup` = avg10 / avg50; `is_drying_up` < 0.7.
- `high_vol_breakout`: `last_vol > 1.5 × avg50` AND `close > 21-bar prior high`.

### `vcp.py` — Volatility Contraction Pattern
`detect(df, lookback_days=90)`. Algorithm:
1. Find swing highs/lows via 5-bar window local extrema; collapse consecutive
   same-type swings.
2. Pair each high with the next low → contraction with `depth_pct`.
3. Quality flags:
   - `monotonic_shrinkage` — each depth ≤ prev × 1.1 (10% tolerance).
   - `tight_right_side` — final contraction ≤ 10%.
   - `volume_drying` — avg vol in final contraction window < 0.8 × base avg.
   - `too_deep` — base depth > 60%.
   - `good_contraction_count` — 2 ≤ n ≤ 6.
   - `ideal_depth_range` — 10 ≤ base_depth ≤ 35%.
4. `has_base` ↔ n≥2 AND monotonic AND tight_right AND not too_deep.
5. `pivot_buy_price` = top of final contraction; `suggested_stop` = bottom.

### `power_play.py`
`detect(df)`. Looks for: a 40-bar (~8 wk) gain ≥ 100% in last 80 bars (with
≥15 bar consolidation tail). Then consolidation depth ≤ 25%, final-10-day
range ≤ 10%, ≥12 bars of digestion. Pivot = consol high, stop = consol low.

### `base_count.py`
`count_bases(df, lookback=504)`. Walk price; whenever a new running-max is set
after ≥15 bars without a new high AND >30 bars since last break → bases++.
Returns `{base_count, is_early_base (≤2), is_late_stage (≥4)}`. Uptrending
stocks default to base 1.

### `sell_signals.py`
`evaluate(df, stage2_start_idx=None, entry_price=None, stop_price=None)`.
Booleans:
- `largest_1d_decline_since_stage2` — today's daily ≤ stage-2 min.
- `largest_1w_decline_since_stage2` — today's 5-bar ≤ stage-2 min.
- `close_below_50ma_on_high_vol` — price<MA50 AND last_vol > 1.3×avg50.
- `close_below_200ma`.
- `climax_run_25pct_in_3w` — 15-bar gain ≥ 25%.
- `stop_loss_breached` — caller supplies `stop_price`.
- `down_10pct_from_entry` — price < entry by >10%.

`action`: `FULL_EXIT` if below 200MA or stop hit; `REDUCE` if severity≥2 or
50MA-vol or climax; `TIGHTEN_STOP` if severity≥1; else `HOLD`.

### `market_context.py`
`market_state()` runs Trend Template on SPY + QQQ. Both pass → `confirmed_uptrend`,
`safe_to_long=True`. Either one → `mixed`, still `safe_to_long=True`. Neither →
`caution`, `safe_to_long=False`.

### `risk.py` — position sizing
Dataclass `PositionPlan(entry, stop, risk_per_share, risk_pct, shares,
dollar_risk, dollar_position, position_pct_of_account, reward_target_2r,
reward_target_3r, move_stop_to_breakeven_at, warnings)`.

`plan_position(entry, stop, account_size, risk_per_trade_pct=1.0,
max_stop_pct=10.0, max_position_pct=25.0)`:
- Validates `0 < stop < entry` and `account_size > 0`.
- `shares = floor(dollar_risk / risk_per_share)`.
- Caps position at 25% of account; 2R and 3R targets; break-even-at = entry+3R.
- Warnings: stop > 10% (max), stop > 8% (book avg-loss target), capped position.

### `catalyst.py`
`catalyst_for(symbol)` runs three sources in parallel:
1. Google News RSS (`news.google.com/rss/search?q={symbol} stock`) — top 15 items;
   keyword scored against `BULLISH`/`BEARISH` sets.
2. Finnhub `/calendar/earnings` — next 30 days (date, hour bmo/amc, eps_estimate,
   revenue_estimate).
3. yfinance `Ticker.earnings_history` (last surprise %), `Ticker.recommendations`
   (last 30 days up vs down revisions, classified by To Grade keywords).

Returns `{symbol, earnings_upcoming, last_earnings_surprise_pct,
analyst_up_revisions_30d, analyst_down_revisions_30d, news_sentiment_score,
news_count, top_news[≤5], provider}`.

`provider = "polygon"` if `POLYGON_API_KEY` set (currently routing not
implemented — `has_polygon()` is just a flag).

### `insider.py` — SEC EDGAR
`insider_activity(symbol)` runs three EDGAR FTS calls (`https://efts.sec.gov/LATEST/search-index`)
in parallel: form 4 (60d), SC 13D (180d), SC 13G (180d). Computes:
- `form4_count_60d`, `form4_count_30d`.
- `form4_unique_insiders_30d` — distinct `display_names` in 30d.
- `form4_cluster_buy` — unique_insiders ≥ 3.
- `has_recent_13d` — any 13D filed in last 30d.
- `recent_filings.{form4[≤5], 13d[≤3], 13g[≤3]}`.

Requires `SEC_USER_AGENT` (env var, defaults to `"Cheetah Market Research
research@cheetah.local"`). SEC mandates a contact UA.

### `ipo_age.py`
`age(symbol)` pulls `period="max"` price history; `years_since_ipo = (now - first
trade date)/365.25`. Flags `is_young` ≤ 8 years, `is_recent_ipo` ≤ 2 years.

### `scanner.py` — orchestrator
`_analyze_symbol(symbol, rs_map)` runs prices→trend→stage→volume→vcp→power_play
→base_count→sell_signals. Composite **score**:
- `+40` if Trend Template passes all 8.
- `+ min(rs,99) × 0.3` (~up to 30).
- `+10` if Stage 2.
- `+5` if accumulation.
- `+15` if VCP `has_base` OR Power Play.
- `+5` if early base (≤2).
- `-10` if late stage (≥4).
- `+5` if high-volume breakout.

`is_candidate` ↔ trend passes AND stage 2 AND entry_setup present AND not late_stage.

`scan_universe(symbols=None, with_catalyst=False, persist=True)`:
1. Drop SPY/QQQ/IWM from candidate pool.
2. Compute RS ranks across whole pool.
3. ThreadPoolExecutor(8) running `_analyze_symbol`.
4. Sort by score, filter `is_candidate`.
5. `market_context.market_state()`.
6. If `with_catalyst`: top-20 candidates → asyncio.gather with semaphore=4 →
   `catalyst_for` + `insider_activity`.
7. Persist to `~/.cheetah/scans/latest.json`.

`load_latest()`, `load_watchlist()`, `save_watchlist()`, `add_to_watchlist`,
`remove_from_watchlist` — JSON IO.

### `brief.py` — morning brief
`generate_brief(with_catalyst=True)`:
- Read latest scan + watchlist.
- Slim top-5 candidates (symbol, score, rs_rank, stage, entry_setup,
  trend_passed, vcp_summary).
- For each watchlist item: pull last price, compute pnl_pct +
  distance_to_stop_pct, run `sell_signals.evaluate`.
- Asyncio sem=4 sweep over candidates+watchlist for catalyst+insider; only
  records with earnings or non-zero sentiment / cluster-buy / fresh 13D are
  retained.
- Write `~/.cheetah/scans/brief.json`.

### `cli.py`
Subcommands invoked by launchd / supercronic. All read the same env vars as
the API container.

| Subcommand | Purpose | Typical cron slot |
|---|---|---|
| `scan [--no-catalyst] [--symbols A,B] [--mode MODE]` | Full per-symbol analysis. Refreshes research cache as a side-effect. | (manual / fallback) |
| `fast-scan [--mode MODE] [--no-fallback]` | Hot scan — joins cached research with today's prices. | Mon-Fri 4:30pm ET |
| `research-refresh [--mode MODE] [--no-canslim] [--workers N]` | Heavy weekly batch. VCP / Power Play / CANSLIM / liquidity / ADR / IPO age. | **Sunday 8pm ET** |
| `research-status` | Print research-cache freshness JSON. | (manual) |
| `brief` | Generate the morning brief from the latest scan. | Mon-Fri 8:30am ET |
| `alerts` | Position-aware + on-demand price-alert checks. | every 5 min during market hours |
| `rescan SYM` | Force price refresh for one ticker. | (manual) |

### `notify.py` — Twilio WhatsApp delivery
Lazy-imports `twilio.rest.Client` so the module is importable without the
package. Reads `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`
(default `whatsapp:+14155238886`), `TWILIO_TO`. Public:
- `send_whatsapp(body) -> bool` — returns False (and logs a warning) if any
  env var is missing or the API call raises.
- `format_brief(brief)` — multi-line digest of the morning brief payload.
- `format_position_alert(item)` — single-position stop-loss / sell line.

### `alerts.py` — position-aware alerts (cron, every 5 min during market hours)
`check_positions()` iterates the watchlist; for each position with `shares>0`:
- pulls real-time price via `prices.last_trade_price()` (Massive `/v2/last/trade`),
- compares to `stop` (stop-loss hit) and `entry * 1.20` (take-profit at +20%),
- runs `sell_signals.evaluate` for distribution / break-of-50DMA flags.
- Fires once per (symbol, kind) per 6h cooldown, persisted in Mongo
  `position_alerts` (or in-memory dict if Mongo unreachable).
- Each fire writes to `price_alert_fires` (so the browser polling endpoint
  surfaces it) and calls `notify.send_whatsapp(format_position_alert(...))`.

### `price_alerts.py` — on-demand per-stock price alerts
Backed by two Mongo collections:
- `price_alerts` — active alerts: `{_id, symbol, kind, level, created_price,
  created_at, last_fired_at, channels[], note?}`. `kind ∈ {below, above,
  drop_pct, rise_pct}`. `_pct` kinds compare current price vs. `created_price`.
- `price_alert_fires` — append-only log: `{_id, alert_id, symbol, kind, level,
  price, fired_at, channels, message}`. Polled by the frontend via
  `/sepa/alerts/recent?since=<ts>`.

Public:
- `create(symbol, kind, level, channels, note)` — captures `created_price` via
  `prices.last_trade_price()` so `_pct` kinds have a reference baseline.
- `list_active()`, `delete(alert_id)`.
- `check_alerts()` — pulls current price for each active alert, evaluates
  trigger, applies 6h cooldown, persists fire row, dispatches WhatsApp if
  `"whatsapp" in channels`. Browser channel is passive (UI polls `recent_fires`).
- `recent_fires(since)`.

### `smart_money.py` — Smart Money & Sentiment (3 lanes)
Per-ticker fan-out, cached 15 min in Mongo `smart_money_cache`.

- **Lane 1 — analyst consensus** (Finnhub free tier). `/stock/recommendation`
  monthly buckets (strongBuy/buy/hold/sell/strongSell) + `/stock/price-target`
  (mean/median/high/low/n). Surfaces month-over-month bullish-rating delta as a
  sentiment-shift tell. Free tier exposes aggregate ratings only — **not**
  per-analyst hit rates. The "80% top-analyst accuracy" stat from TipRanks is
  not reproducible without a paid feed; see Lane 1 research notes.
- **Lane 2 — curated blogs** (RSS). Allowlist: Damodaran (Blogger Atom),
  Bespoke "Think B.I.G." blog, Morningstar stock-analysis feed. Body regex
  `\$?TICKER\b` (with non-letter borders) against title + stripped body.
  Top 8 most recent.
- **Lane 3 — Reddit** (PRAW, optional). Allowlist:
  r/SecurityAnalysis (score ≥30), r/ValueInvesting (≥100), r/investing (≥250),
  r/stocks (≥500), r/options (≥150). 30-day window. r/wallstreetbets
  intentionally skipped. Disabled when `REDDIT_CLIENT_ID` not set — UI shows a
  configure-to-enable hint.

**13F institutional data is intentionally excluded** despite being the obvious
fourth lane. The 45-day filing lag plus the empirical underperformance of 13F-
clone ETFs (ALFA liquidated 2022, IBLN delisted, GURU underperforms SPY) makes
13F net-misleading on a 1-12wk swing-trading timeframe. Cohen-Polk-Silli's
~3% annual "best ideas" alpha holds at *quarterly* rebalance, not weekly.

Frontend wiring: data lands on the SepaCandidate detail (`/sepa/:symbol`) under
`smart_money` key. Surfaced three places:
- Dedicated **smart money** tab (full breakdown via `SmartMoneyPanel`).
- Setup tab — analyst mean target callout under the R-multiple ladder, with a
  "below your +2R target" warning when applicable.
- Catalyst tab — "Top discussion" callout listing 2 blog mentions + 3 Reddit
  threads, linking to the dedicated tab.

### `dual_momentum.py` — Antonacci's two-gate ranking
Reuses the latest persisted scan (`scanner.load_latest()`) for universe + names
+ RS rank, then recomputes 1/3/6/12-month returns from cached daily bars (no
provider re-hits).

- **Absolute momentum gate**: `return_12m > 0`. Page also reports SPY's 12m
  return as the regime indicator — when SPY 12m ≤ 0, label flips to
  `DEFENSIVE — classic Antonacci says cash/bonds`.
- **Relative momentum**: ranks eligible names by a weighted composite —
  50% 12m + 25% 6m + 15% 3m + 10% 1m return.
- Each row carries `is_sepa_candidate` and the SEPA `entry_setup`, so a row
  flagged both `abs` AND `SEPA` is the strongest signal in the app.
- Frontend page: `/dual-momentum` (NavBar entry "Dual Momentum"). Lookback +
  top-N + min-RS controls; toggle between picks-only and full universe.

### `research.py` — Heavy research cache (the weekend layer)

**Architecture: SEPA's per-symbol analysis splits into two cost tiers.**

  - **Research** (this module) — refreshed weekly on Sundays. Includes VCP
    base detection, power play detection, base count, CANSLIM fundamentals,
    liquidity baseline, ADR baseline, IPO age, company name, stage snapshot.
    CANSLIM C/A (and the board dilution / return-on-capital columns and the
    long-term Fundamentals tab) read filed statements from Massive's **v1
    fundamentals** (`/stocks/financials/v1/{income-statements,balance-sheets,
    cash-flow-statements}`) through ONE helper, `sepa/massive_fundamentals.py`
    (2026-09-30; the vX financials endpoint sunsets 2026-10-09). A provider
    outage raises `FinancialsUnavailable` and surfaces as a named reason — never
    as "no filings", never as zeros. Field map + semantic changes:
    `docs/sepa/massive_fundamentals_v1.md`. Since 2026-10-08 the revenue line
    follows v1's statement template (banks: revenue net of interest expense —
    the 10-Q's total net revenue; C alone adds other income, a CIK pick); the line rides on the
    research doc as `fundamentals.rev_line*` — `docs/sepa/revenue_lines_2026_10_08.md`.
    Costs ~1-2s per symbol (so 20-30 min on Russell 1000).
  - **Hot** (`scanner.scan_universe_fast`) — runs on demand or daily. Joins
    cached research with today's prices and recomputes only the price-derived
    layers (trend template, today's stage, today's volume, entry-setup match
    against cached pivot, composite score). ~20-30s per scan.

**Why split?** VCPs don't change day-to-day — once a base forms it stays. The
expensive contractions analysis is wasted work if you re-run it daily. By
caching the research blob and joining today's prices on top, Monday's scan
goes from 20+ min to 30s while still using current data.

**Mongo collection:** `sepa_research_cache` (8-day TTL — one cycle plus a
grace day if Sunday's cron skips). Per-symbol document keyed by `symbol`
with `cached_at` epoch.

**Cron:** Sunday 8pm ET via `sepa.cli research-refresh`. Configure the
universe via `SEPA_UNIVERSE_MODE` env var (curated / sp500 / russell1000 /
expanded) or `SEPA_UNIVERSE_FILE` for an explicit file path.

**Fallback semantics:** if `scan_universe_fast` encounters a symbol missing
from the research cache, it falls back to the full per-symbol analysis for
that one symbol (so coverage gaps don't drop tickers from the result).
Counts are reported in the scan payload as `research_cache_hits` /
`research_cache_misses`.

### `universe.py` — Multi-mode universe loader

Resolves the active scanning universe from these sources, in priority order:

1. Explicit `mode` argument to `load_universe(mode=...)`
2. `SEPA_UNIVERSE_FILE` env var — path to one-ticker-per-line text file
3. `SEPA_UNIVERSE` env var — comma-separated literal
4. `SEPA_UNIVERSE_MODE` env var — one of `curated`, `sp500`, `russell1000`, `expanded`
5. Default: `curated` (the hand-picked ~130 names in this file)

**Remote fetchers** are cached 30 days under `~/.cheetah/universe/<mode>.txt`:

- `fetch_sp500()` — Wikipedia's `List_of_S%26P_500_companies` parsed via
  `pandas.read_html`. ~500 names. Tickers normalized: `BRK.B` → `BRK-B`.
- `fetch_russell1000()` — iShares IWB ETF holdings CSV. ~1000 names. Same
  ticker normalization.

Benchmarks (`SPY`, `QQQ`, `IWM`) are always appended for RS-rank math.

### `stock_analysis.py` — Fidelity-style multi-panel readout
Per-ticker; cached 60 min in Mongo `stock_analysis_cache`. Four panels:

1. **Fundamental analysis** — yfinance `.info` fields scored 0-100 across:
   Valuation (P/E, P/B, P/S inverted), Quality (ROE, ROA, margins), Growth
   Stability (revenue + earnings YoY), Financial Health (D/E, current ratio,
   FCF positivity).
2. **Technical sentiment** — three time horizons, derived from cached prices:
   Short-term (21-day return + 10/20-day MAs), Mid-term (stage classifier +
   50/200-day stack + 6-month return), Long-term (12-month return + 200-day
   trend slope). Output Weak / Neutral / Strong cells.
3. **ESG** — yfinance `Ticker.sustainability` (Sustainalytics risk scores,
   inverted to 0-10 quality). Bands: Laggard / Average / Leader. Returns
   `available: false` for tickers without ESG data.
4. **Analyst consensus** — Finnhub `/stock/recommendation` (12 monthly
   buckets) + `/stock/price-target`. Synthesizes a 0-10 Equity Summary
   Score and label (Very Bullish → Very Bearish), the latest distribution,
   12-month price target stats, and a 1-year history timeline.

Frontend: surfaced as the **analysis** tab on the SepaCandidate detail page
(`StockAnalysisPanel` component). All four panels render side-by-side; any
panel with `available: false` collapses to a single empty placeholder.

### `company_names.py` — symbol → company name resolver
Backs the `name` field shown beneath each ticker on the SEPA candidate cards
and the Dual Momentum table. Mongo collection `company_names_cache` (30-day
TTL); cache misses fetch via yfinance `.info["longName"]`. The scanner calls
`bulk_warm()` before iterating so a scan pays the lookup cost once.

### `providers.py`
Tiny env-var holder. `POLYGON_API_KEY`, `FINNHUB_API_KEY`, `has_polygon()`,
`has_finnhub()`. Polygon routing **not yet wired** — see § 9.

### Supply/Demand level pad — `supply_demand/level_pad.py` (2026-09-30)
Ajay's 1% pad under demand floors and support key levels ("if the demand zone or key
level is 133, it holding at 132"). ONE constant, `DEMAND_PAD_PCT = sd_liquidity.STOP_SHELF_PCT`
(1.0; 0 = off everywhere). Every SUPPORT read (in the zone / near demand / arrival / crossed /
broken / the stop) goes through `support_floor(band)` / `in_band` / `under_floor` / `key_edge`;
RESISTANCE reads, dedupe keys, drawn band edges and the measured floor-held gate keep the drawn
edge (`PAD_FLOOR_HELD = False`, his call). Payloads gain `pad_lo` / `pad_pct` / `pad_price`,
never a moved edge. UNMEASURED (`zone_pad_measured.py`, pending). Full rule, sites, phone-gate
statement, sell-timing list and HIS CALLs: `docs/supply_demand/zone_pad_2026_09_30.md`.

### Supply/Demand index zones — supply_demand/index_zones.py (2026-09-16; macro rows 2026-10-15)
The 🧭 strip pinned on Chart Maps ▸ Back in Demand. `INDEXES = ("SPY", "QQQ")` (the cards) and, since
2026-10-15 (*"how can.I check us bonds and us dollar and gold … I wanna see their progress"*), `MACRO` =
TLT "US bonds (20y+)" / UUP "US dollar" / GLD "Gold" — ETF PROXIES, MINE, his to swap; `STRIP_SYMBOLS =
INDEXES + MACRO_SYMBOLS`. The 04:15 ET weekday job (`python -m supply_demand.index_zones`, no new cron line;
deploy needs `cron`) stores one doc per day: board + fine resolutions and closed-bar `bars` per symbol.
Sources: `zone_store` (SPY/QQQ) | `computed` (TLT/UUP/GLD — not in `full`; `zone_store.build_doc` off a FRESH
`prices.closed_daily_frame(…, use_cache=False)` that never reads or writes the shared price cache) |
`unavailable` (stored with a reason). Every served entry gains a serve-time `progress` (5d / 21d =
`rotation.tracker.trailing_return` over the stored bars; today = live print vs `official_prev_close`, read only
when the stored close is the prior session's; text = `high_beta_tab.leg_text` of the raw move). Served by
`GET /supply-demand/index-zones` and attached to the zones board (`board._index_strip`, riding the board's one
live fetch); the header's `as_of` is measured on SPY/QQQ. Context only — gates nothing, alerts nothing, not
advice. Full contract: `docs/supply_demand/index_zones.md`.

### Chart Maps — Gajjala's tab — `chart_maps/gajjala/` (2026-10-13)
Goverdhan Gajjala's five intraday setups over HIS scanner on the whole US market (Ajay: *"Implement his full stategy do
not assume anything."*). Long setups only. **UNMEASURED** — nothing here trades, sizes or enters a lane; not SEPA (no
other method's gate, import or citation — `test_gajjala_source_guard.py`). Every number lives in `constants.py` and is
imported, never retyped; tags as the file writes them: **GG** = his own words (S8 IBD webinar, S9 TraderLion podcast, X
posts; a trailing `# GG <ts>` that `test_gajjala_verified_rules.py` ties to `verified_rules.json`), **Ajay** = his
2026-10-13 answers (DECISIONS rounds A/B/C), **Cheetah default** = Ajay's number, not GG's (the ℹ️ panel says so),
**spec default** = an unanswered display option shipped OFF, **TRANSPORT** = pacing only.
- **Sub-tabs** (`SUBS`, default `DEFAULT_SUB` = `bull_flag`): 🚩 Bull Flag · 💋 EMA Kiss & Fly · ➖ Horizontal Fade · 🌀
  Intraday VCP · 🎾 Reversal Squeeze · ☀️ Premarket · 🌙 Post-market · 📓 Playbook (his words with timestamps, text only).
  Charts are closed 5-minute bars (the Fade reads 15-minute first) resampled from the 1-minute cache, with the 9/21 EMA
  (`EMA_FAST` 9 / `EMA_SLOW` 21, imported from `orderflow.signals` — GG S8 25:36, S9 24:42).
- **Scanner** (one whole-market Massive snapshot per pass): `SCAN_MIN_PRICE` 0.10 (GG X 2024-02-01, his latest — Ajay
  round A) to `SCAN_MAX_PRICE` 100.0 (GG S8 19:12), `SCAN_MIN_VOLUME` 1,000,000 (GG S8 19:12), `SCAN_MIN_CHANGE_PCT` 25.0
  vs the prior close (GG S8 19:51); `SCAN_INSTRUMENT_TYPES` CS + ADRC, `SCAN_INCLUDE_OTC` False,
  `SCAN_UNKNOWN_TYPE_POLICY` "list" ("type unknown") — Ajay; `STAY_LISTED_SESSIONS` 2 (Cheetah default);
  `NO_TRADE_AFTER_OPEN_MIN` 15 (GG S8 14:41). Strip: `SA_BIG_RUNNER_PCT` 100 / `SA_RUNNER_PCT` 80 / `SA_QUIET_BEST_PCT` 40
  (GG S8 43:39–44:37).
- **Setup knobs** (all Ajay K1–K10 / H1–H5 unless tagged): K1 demand bar `K1_BODY_GAIN_PCT` 3.0, `K1_RANGE_MULT` 1.5 over
  `K1_RANGE_LOOKBACK` 20; K2 `K2_MAX_VOL_STEP` 5.0 within the leg (`K2_CHECK_FIRST_BAR` False); K3 `K3_DEPTH_FRAC` 0.50 /
  `K3_VOL_FRAC` 0.50, the depth floor on `K3_DEPTH_SETUPS` (Bull Flag, Kiss & Fly) only. Legs: `BF_LEG_MIN_BARS` 2 (GG S9
  1:59:24), `KF_LEG_MIN_BARS` 1 (GG S8 31:33), `HF_LEG_MIN_BARS` 2, `VCP_LEG_MIN_BARS` 1. Bull Flag pullback
  `K4_BF_PULL_MIN`–`K4_BF_PULL_MAX` 1–3; Kiss & Fly `K5_KISS_TOL_PCT` 0.5, `K5_SLOPE_BARS` 3, ≤ `K4_KF_PULL_MAX` 9, every
  pullback close ≥ 9 EMA (`KF_HONOR_ALL_PULLBACK_CLOSES`); Fade base `K4_HF_BASE_MIN`–`K4_HF_BASE_MAX` 6–24, `K6_MERGE_PCT`
  0.5, `K6_TIGHT_PCT` 8.0, `K6_SELL_DECAY` 0.70, trigger `HF_TRIGGER` "base_high"; VCP ≥ `K4_VCP_MIN_CYCLES` 2,
  `K7_CONTRACTION` 0.75, `K7_EMA21_TOL_PCT` 0.5, `VCP_PIVOT_WINDOW` 2; Reversal Squeeze `K8_MAX_FLOAT` 10,000,000,
  `K8_DROP_PCT` 8.0, `K8_RECOVER_PCT` 2.0 in `K8_RECOVER_BARS` 3, failed attempt `K8_FAIL_NEAR_PCT` 2.0 /
  `K8_FAIL_DROP_PCT` 8.0 / `K8_FAIL_EVENT_RULE` "distinct", `RS_BASE_MIN_BARS` 1, history chip `K8_HISTORY_SESSIONS` 30 /
  `K8_HISTORY_RANGE_PCT` 50.0, `FLOAT_SUSPECT_POLICY` "ineligible" (spec default); ☀️ K9 `K9_PM_MIN_VOLUME` 1,000,000,
  `K9_AH_CARRY_PCT` 10.0; 🌙 K10 `K10_CLOSE_TOP_FRAC` 0.30, `K10_AH_MIN_VOLUME` 250,000, `K10_AH_MIN_GAIN_PCT` 5.0.
  Entry = the entry bar's high trades above the trigger on a CLOSED bar; stop = the trigger bar's low (the bar before the entry bar) / the base's low.
- **Reads**: **A+** = every rule met and the entry bar closed — the only pushable state. Listed, never A+, never pushed:
  **"long flag"** (Bull Flag pullback past `K4_BF_PULL_MAX`, up to `K4_BF_LONG_FLAG_MAX` 5; more = invalid),
  **"near-kiss"** (`KF_NO_TOUCH_VARIANT`, `KF_ALLOW_NO_TOUCH` True: K3 + uptrend pass, no bar kissed the 9 EMA),
  **"B — imperfect"** (`VCP_B_GRADE`, `VCP_B_READS` True: exactly one of the K7 contraction / 21-EMA hold missed).
  Other states: triggered · forming · partial · stopped; invalid / none are counted, never tiled. Chips are display only:
  🧱 `PSY_LEVELS` $1/$5/$10 (GG S9) within `PSY_NEAR_PCT` 5.0 (Cheetah default); red closes > `RED_CLOSES_WAIT` 3 (GG X),
  `RED_CLOSES_MODE` "chip" (Ajay — never a criterion); halts and after-hours exhaustion OFF (`HALT_CALM_BARS`,
  `AH_EXHAUSTION_MAX_PCT` None — spec default).
- **Push** `gajjala_setup` (`PUSH_KIND`, owner-only — `hooks.notify_gajjala_setup` → `send_to_user(owner)`; default
  pref False for everyone else, owner keep-set ON: his devices through `OWNER_KEEP_SET` + `scripts/owner_prefs_apply.py`
  — the 🧠 / 🎚️ precedent, AMENDMENTS10 F1): `GAJJALA_PUSH_MODE` **"live"** since 2026-10-16 (`# Ajay 2026-10-16`:
  *"you alert me when that happens"*) — his call, not a measurement; "shadow" 2026-10-13…16 (Ajay round A), when each
  A+ was recorded in `gajjala_alerts` as "shadow — not sent" on /alerts (those rows stay listed that way). The full gate
  runs every pass; each A+ entry is claimed once per (symbol, setup, ET day) under `GG:{date}|{SYM}|{setup}` and sent —
  every A+ its own push; refusals are recorded `{key}#{state}` and never consume the day's claim. Only the exact string
  "live" sends (any other value runs as shadow — a flip back is one word); a live claim checks the `SHADOW:` twin first,
  so an A+ recorded in shadow earlier that day never rings (no double ring across the flip). The on-open / dry pass
  never claims or sends; a `--now` replay that is not `--dry-run` refuses (F7). The `STUDY_SESSIONS` 250-session study
  (`scripts/gajjala_study.py`, exits stop-or-16:00 · stop-or-`STUDY_TIME_EXIT_MIN` 60-min · breakeven after
  `STUDY_BE_AFTER_R` 1.0R then the first 5-min close under the 9 EMA; placebo = same-session scanner names with no
  setup) read **NULL** 2026-10-14 (`docs/gajjala/study_2026_10_13.md`) — UNMEASURED. Window (`alerts._closes`, no typed
  times): `ET_RTH_OPEN` + `NO_TRADE_AFTER_OPEN_MIN` up to `rth_close_time()`, then up to `ET_AFTERHOURS_CLOSE`
  (`HALF_DAY_AH_CLOSE` on `HALF_DAYS`), never the first `NO_TRADE_AFTER_OPEN_MIN`, never pre-market, closed days silent.
- **🎯 A+ entry LIVE** (2026-10-16, Ajay's call — *"you alert me when that happens"*). Ajay: *"can you add liver tracker
  for Gajjala's entry."* and *"Dont understand the question I amlooking for Entry of his stocks from all 5 tabs. When
  every they satisfy all his criteria.. LIke for some he says we need to make sure EMA is kissed you alert me when that
  happens 5 mins track of it when there are potentials and also look for new potentials"*. All five setups; title
  "{emoji} {SYM} · {label} A+ entry"; body numbers first (AMENDMENTS10 F9) "broke {T} on the {frame} bar closing {HH:MM}
  ET · stop {S} (−{r}%) · {ENTRY} · 🧠 potential rang {HH:MM} ET · {float} · [after-hrs line] · UNMEASURED — his setup,
  not a buy signal". `{ENTRY}` = `alerts.ENTRY_WORDS[setup]` via `entry_words()`: one clause per setup in the words of
  his rules in `verified_rules.json` (each line cites its rule ids; 🎾 has no first-hand entry rule on file — RS2 / RS4
  are 2+ sources), EMA lengths from `EMA_FAST` / `EMA_SLOW` at call time, never typed, never composed by the FE. The 🧠
  clause only when today's 🧠 potential of the same (symbol, setup) RANG (`alerts.potential_rang_at`, read after every
  refusal and the dry gate, own try — a read fault = no clause, never a skipped push). 📈 Track rows serve `entry_text`
  "🎯 entry sent HH:MM ET" (`tab.ENTRY_SENT_TEXT`, `tab._entry_times` = one `store.alert_rows` read per 🧠 build
  classified by `ledger.alert_of`; pushed `GG:` claims only). 🏁: a pushed `GG:` doc is line live, `KIND_TEXT` "🎯 A+
  entry", counted under `counts["entry"]` and served as `entries_text` — its own 🎯 line, never pooled into the 🧠
  headline % (an A+ exists only once the trade survived its entry bar, AMENDMENTS10 F3). UNMEASURED — the 2026-10-14
  study read NULL. Contracts "🎯 Gajjala entry live (2026-10-16)"; ✨ `chart-maps-gajjala-entry-live-2026-10-16`; HIS
  CALLS Q1–Q11 + deploy order: `docs/gajjala/entry_live_2026_10_16.md`.
  - ☀️/🌙 movers and 🌙 A+ recap rows are router links — same place as other Gajjala rows (his answer; Ajay: *"Also in the after market movers under Gajjala's can you make sure I can click on them."*): a bar-less tile links its served `tile.href` through `withSource` + the back state (the charted tile's target), a recap row its served `href` = `potential.deep_link(sym, setup)` (`tab.recap`), both behind `ggHref`; CardExtras lines stay text; contracts 🎯 check 11.
- **Cron** (`backend/crontab`; the host copy is a separate install step — a deploy does not ship it):
  `1-56/5 4-20 * * 1-5 /usr/local/bin/python -m market_hours.gate chart_maps.gajjala.run` (the pass, `PASS_CADENCE_SEC`
  300, `PASS_OPEN_ET` 04:00–`PASS_CLOSE_ET` 20:05, TRANSPORT) and
  `15 20 * * 1-5 /usr/local/bin/python -m market_hours.gate chart_maps.gajjala.nightly` (float, halt history, 🎾 history,
  🏁 track-record grade — last step, 2026-10-16).
- **Endpoint** `GET /chart-maps/gajjala?sub=&tf=&focus=&sort=&limit=&span=` (`span` 🏁 only, 2026-10-16) (`limit` `TILE_LIMIT_DEFAULT` 24, max
  `TILE_LIMIT_MAX` 80) → `tab.build()`: reads Mongo only (`gajjala_reads`, `gajjala_passes`, `gajjala_alerts`) plus one
  live fan-out for the shown tiles' now-line; never scans or fetches a bar on the request. `stale` after `STALE_AFTER_SEC`
  900. ℹ️ panel: `rules_info` section "gajjala", built from `constants.py`.
- **Not built** (📓 Playbook text only, each would need Ajay's numbers): exits / partials / breakeven-and-add are never
  computed (his discretion), sizing and the drawdown brake, a trades-per-day cap, a confluence score, the post-market
  journal (R2-8: not now).
- **Docs**: `docs/gajjala/gajjala_tab_2026_10_13.md` (tab, endpoint, Playbook, ℹ️), `push_2026_10_13.md`,
  `study_2026_10_13.md`, `detectors_2026_10_13.md`, `context_reads_2026_10_13.md`, `data_plan_2026_10_13.md`,
  `sources_2026_10_13.md`, `frontend_2026_10_13.md`, `volume_avg_backend_2026_10_13.md`, `entry_live_2026_10_16.md`
  (🎯 A+ entry LIVE, 2026-10-16).
- **🧠 Potential · 📈 Track · 🔔 `gajjala_potential`** (2026-10-15, `chart_maps/gajjala/potential.py`). Ajay: *"In
  Gajjalas setup I wanna find potential stocks … So create a potential category in this section."*, *"In all the sub tab
  and add a track and alert to show me new potential is added everyday."*, *"Give me an alert all continous tracker on
  these specifically when I get alert I will jump on to ride the wave"*. **UNMEASURED — a potential, not an entry; GG
  enters on the reclaim of the highs.** Potential (his K1) = a setup read in state `POTENTIAL_STATE` `forming` (the
  detectors' own K-criteria decide forming vs partial — no new detector, no score); `ready` True = "trigger armed",
  else "building"; `partial` / `aplus` / `triggered` never. Three conditions on top are Cheetah defaults, not his
  (`CHEETAH_DEFAULTS`, HIS CALLS P0–P2): `POTENTIAL_NEEDS_BASE` (≥ 1 sideways bar), `POTENTIAL_FRESH_TAPE` (a print in
  the 5-minute bar that just closed, `alerts.MAX_ENTRY_AGE_SEC` reused), `POTENTIAL_DEFER_REFUSED` (a held first
  sighting rings at the next pass while still forming); the join rule (AMENDMENTS4 D9, HIS CALL P12, no constant) tracks
  but never rings what a mid-session restart finds already forming. GG's tells (float, 🔄 rotation, ⏸ halts, 🌙
  after-hours mover, 📅 prior-day listing, 🧩 another setup) are badges and order, never gates. Surfaces: a 🧠 strip in
  every setup sub, and the sub `POTENTIAL_SUB` (last in `SUBS`) = roll-up + 📈 Track + 👀 watch line. Tracker: Mongo
  `gajjala_potentials` (`store.POTENTIALS`, kept for the later study), one doc per (session, symbol, setup) stamped on
  the pass clock, written only by the existing 5-minute pass (`run.run_pass` → `PT.run_pass`, own try/except). Push
  `POTENTIAL_PUSH_KIND` `gajjala_potential`: LIVE, owner-only (`OWNER_KEEP_SET`, default pref False), MARKET kind (silent
  on closed days), one push per (date, symbol, setup) — K3, no cap — on the pass clock `ET_PREMARKET_OPEN`–
  `ET_AFTERHOURS_CLOSE` (04:00–20:00 ET, the half-day close on `HALF_DAYS`), never `ET_RTH_OPEN` + `NO_TRADE_AFTER_OPEN_MIN`
  (09:30–09:45, K2); `/alerts` 🧠 pass row + today's list, `/notifications` toggle, ℹ️ lines. No new crontab line.
  The A+ kind stays SHADOW, its copy narrowed to "no A+ reaches your phone" (until 2026-10-16 — now LIVE, see 🎯). Contracts: `scripts/contracts.mjs` "🧠
  gajjala_potential (2026-10-15)". Doc: `docs/chart_maps/gajjala_potential_2026_10_15.md`.
- **🔄 Scan on open · 🎯 A+ banner** (2026-10-15, `chart_maps/gajjala/on_demand.py`). Ajay: *"When ever I open
  Gajjala's intiate a new scan of stocks.  In that moment and if there are any enterable stocks on the top which I see
  in potential i guess"*. Mounting the board (opening, or switching into `tab=gajjala`) POSTs `/chart-maps/gajjala/scan`
  — owner-only (`auth.is_admin_email`, 404 stealth) — which answers at once (started | reused | waiting | closed |
  refused) and spawns ONE pass as a SUBPROCESS (`python -m chart_maps.gajjala.run --on-demand` → `run.run_on_demand`;
  the api process runs no pass work, AMENDMENTS5 A1): `ON_DEMAND_BUDGET_SEC` bar budget, no Yahoo, BOTH push gates dry,
  no /alerts row, pass doc `{date}|{HH:MM:SS}|open` with `on_demand: true` — unless a pass is in flight (waited for),
  the latest finished under `ON_DEMAND_REUSE_SEC` (60 s, Ajay K4), or the session's first 5-minute pass has not landed
  (`waiting`, A12). Lease split (`store.claim_lease(now, source)`): the min gap counts cron starts only
  (`last_cron_started_at`, the tick clock — A6); an on-open claim needs only "not held" and writes `od_started_at`, never
  `started_at` (A9); a cron tick that finds an on-open pass holding the lease waits ≤ `CRON_WAIT_ON_DEMAND_SEC` (polled
  every `ON_DEMAND_POLL_SEC`) then takes it over — never refused by an open; releases are token-guarded and a
  superseded on-open pass stops writing (`lease_owner_is`, A8). GET (still Mongo-only) serves `scan` ("🔄 scanned on
  open HH:MM ET · bars through HH:MM" / "last pass HH:MM ET", "scanning…" while the lease is held) and `enterable` (🎯
  every read of the latest pass whose card state is `aplus`, variant / grade reads included with the card's own words,
  newest entry bar first — A11) on every sub, first in 🧠 Potential; served only while the newest CRON pass
  (`latest_cron`) is within `STALE_AFTER_SEC` — opens alone never hide a dead cron (A10). Closed bars only. UNMEASURED.
  Doc: `docs/chart_maps/gajjala_on_open_scan_2026_10_15.md`; contracts "🔄 Gajjala scan on open + 🎯 A+ banner
  (2026-10-15)".
- **🚫 Not eligible at Fidelity** (2026-10-17, Ajay: *"Or just add a tag that not eligible on Fidelity"*) — his own list
  (`BROKER_FLAG_SEED` empty + `gajjala_state` `_id "broker_flags"`, `store.broker_flags` = (seed ∪ added) − removed; a
  store read fault falls back to the seed and the strip says "your list could not be read this time — the tags are off
  until the next read"), served `broker_text` on every Gajjala row that names a symbol + the owner's `broker_flags` strip
  and 🚫 card toggle — owner = the primary admin only (`ollama_chat.api.is_primary_admin`; anyone else null); the A+ / 🧠
  bodies say " · 🚫 not eligible at Fidelity" before UNMEASURED and the titles end " · 🚫"; `alerts.COUNT_KEYS`
  "broker_flagged"; GET / POST / DELETE `/chart-maps/gajjala/broker-flags` (owner, stealth 404; bad ticker 400, read fault
  503); nothing hidden, nothing muted, nothing guessed (a pre-screen from Fidelity's published rules = HIS CALL Q2). Doc
  `docs/gajjala/broker_flags_2026_10_17.md`; contracts "🚫 Gajjala broker tag (2026-10-17)"; ✨
  `chart-maps-gajjala-broker-tag-2026-10-17`.

### Chart Maps — 🏁 Gajjala's Track record — `chart_maps/gajjala/ledger.py` (2026-10-16)
Every Gajjala alert that rang, graded win or loss. Ajay, 2026-10-16: *"also can you track all Gajjals stocks and keep a
new tab to show wins vs losses. To see a percentage and the ticker."* and *"We are not looking for winners just in time
but when they got in to our alerts if they made it or not. Like XLAB today was a winner I made good money on it"*. His
knob answers: **"GG's trade math"**, **"Both columns"**, **"Keep GG's math"**, **"From 09:45 ET only"** (DECISIONS9 +
AMENDMENTS9). **UNMEASURED — a ledger of the alerts as sent, not a backtest and not a study**; small n; the 2026-10-14
study of the five setups read NULL (`docs/gajjala/study_2026_10_13.md`) and this record does not change that. Not SEPA
(source guard). Every number in `constants.py`, tagged: his `# Ajay 2026-10-16`, mine `# MINE` / `Cheetah default (MINE`.
- **Rule** (GG's trade math, his answers): entry = the trigger the alert gave; the fill = the first 1-minute bar that
  starts `BAR_SETTLE_SEC` 30 s or more after the alert, inside `LEDGER_FILL_FROM_ET`–`LEDGER_FILL_TO_ET` (09:45–16:00 ET —
  09:45 is BUILT as `ET_RTH_OPEN` + `NO_TRADE_AFTER_OPEN_MIN`, never typed), whose high is at or above the trigger — at
  the trigger, or at that bar's open on a gap. WIN = a later high reaches the fill + `LEDGER_R_MULT` 1.0 R (R = trigger −
  stop as the alert gave them) before any low touches the stop. LOSS = the stop is touched first — a touch (`low ≤
  stop`) counts, a bar printing both = loss, a stop in the fill minute = loss. Two columns (`LEDGER_HORIZONS` "same",
  "next"): same session = through the regular close of the alert's day (an alert at or after the close: its next
  regular session); through next session = the same walk to the regular close of the market day after that. The % =
  best high after the fill vs the fill; the small % = the column's last close vs the fill. Listed, never counted: no
  entry (the trigger never traded in the window), no plan (no trigger / stop on the alert), no risk (trigger = stop),
  no alert time (E3: `at` → `claimed_at` → none). `LEDGER_MIN_R_PCT` 0.5 (MINE, HIS CALL Q16): R under 0.5% of the
  trigger = "thin R" chip, graded, kept out of the %. Row chips "rang pre" / "rang RTH" / "rang AH" from the alert's
  own stamp.
- **Rows** (D1): every 🧠 `gajjala_potentials` doc whose push RANG (`push.state` "pushed"; joined / muted / never-pushed
  are not rows) = the live line and the headline %; every A+ `gajjala_alerts` claim in state shadow = a separate "A+
  shadow — never sent" line, counted on its own, never in the %; + every live A+ entry (`GG:` state pushed, since
  2026-10-16) on the live line, kind "🎯 A+ entry", counted on its own 🎯 line (`counts["entry"]`, `entries_text`) —
  never pooled into the 🧠 headline % (AMENDMENTS10 F3). Counted per alert (XLAB on 10-16 = two rows).
- **Storage** Mongo `gajjala_ledger` (`store.LEDGER`, `_id` `"{date}|{SYM}|{setup}|{kind}"`, kept, no TTL; top-level keys
  `store.LEDGER_KEYS` only) — written ONLY by `ledger.grade_step` through `store.upsert_ledger`.
- **Nightly grade** (`nightly.STEPS` … `"grade"` LAST, own try — its failure never stops a step): rides the EXISTING
  `15 20 * * 1-5 … chart_maps.gajjala.nightly` line (`LEDGER_GRADE_AT_ET` "20:15"; no new crontab line, no `--steps`).
  Re-reads the last `LEDGER_GRADE_LOOKBACK_SESSIONS` 10 market days; writes a column only once its horizon has ended;
  at most `LEDGER_BACKFILL_MAX_SYMBOL_DAYS` 120 symbol-day loads a run (the rest "not graded yet", next night); a
  provider failure / empty day leaves the column absent (retried), never "no entry"; each row in its own try. A decided
  same column is walked again for the next column's best % (the trade itself copied). Split guard: a split between the
  alert day and a column's end → that column reads "split — not graded"; a trade already decided in the same session
  keeps its outcome and its best / close stay the same session's; an unread split check leaves the column for the next
  night. `LEDGER_GRADE_VERSION` bump re-grades the window.
- **Today read** (`ledger.today_read`, called by the GET on `sub=track_record` only — the one Gajjala GET that fetches
  bars): today's rows without a stored same column, one 1-minute `daytrading.data.load_intraday(…, force=True)` per name,
  at most `LEDGER_TODAY_MAX` 60 names, `LEDGER_TODAY_BUDGET_SEC` 15 s, memo `LEDGER_TODAY_MEMO_SEC` (= `PASS_CADENCE_SEC`),
  closed minutes only, "through HH:MM" never past the read (E6), its own try (the board serves without it). NEVER
  WRITES. Cells read "… so far · not final".
- **Sub** `LEDGER_SUB` `track_record` = 🏁 Track record, LAST in `SUBS` (after 🧠 Potential); chip count = today's rows
  graded (`ledger.count_today`). `?span=` `LEDGER_SPANS` today · yesterday · 5d · 10d (`LEDGER_SPAN_SESSIONS_LONG`) · all, default `LEDGER_SPAN_DEFAULT`
  "5d" (the last `LEDGER_SPAN_SESSIONS` 5 sessions — MINE, HIS CALL Q9); "all" = the alert dates of the rows (E7). Every
  string served by `ledger.served_block` (title, rule, honesty, counts, cells); the FE (`TrackRecordPanel`) composes
  nothing; a read fault serves `tab.TRACK_RECORD_FAULT`.
- **HIS CALLS** Q0–Q16 + the carried items: `docs/gajjala/track_record_2026_10_16.md`. Contracts:
  `scripts/contracts.mjs` "🏁 Gajjala track record (2026-10-16)". ✨ `chart-maps-gajjala-track-record-2026-10-16`.
- **🕰️ Entries timeline + tape** (2026-10-16, Ajay: *"Can you use the graph component from  that to show what happened
  to Entries alert of Gajjala with all the 100% criteria satisfier. One you alert it from the alert system you built
  please"*). **UNMEASURED — a picture of what each A+ alert did, graded by the ledger's own math, not a study**; the
  2026-10-14 study read NULL; the A+ subset is survivor-biased. The 🏁 Track record gains a served view toggle
  (`tape.VIEWS` "📋 all alerts" | "🕰️ entries timeline", `?view=timeline`, FE-only — the view never rides the GET;
  default 📋 all alerts). The timeline lists only the A+ rows (`views.kinds`; 🎯 live + shadow) in the 🏁 served order,
  each with a lazy mini tape and a 📈 expand — the Promo Circuit tape drawn by ONE primitive
  `frontend/src/components/TapeChart.tsx` (PromoTagTape / MiniTape re-implemented on it, byte-identical SVG, proved by
  `PromoTagTape.snapshot.test.tsx` cut before the refactor) plus the trigger / stop / +1R levels, the alert (solid) and
  fill (dashed) rules and the fill / exit dots; the read line = the 🏁 cells' own texts. Every tape word is served by
  `chart_maps/gajjala/tape.py` (`ENTRY_TAPE_WORDS`) behind `GET /chart-maps/gajjala/entry-tape?id=&lite=0|1` (404 for an
  unknown id; NEVER WRITES a gajjala collection; completed days through the house loader, no force; today through the
  ledger's shared memo `ledger.today_bars`; the mini never fetches; lite = every `promo_tape.LITE_STRIDE`-th bar; memo
  `LEDGER_TAPE_MEMO_SEC` per id, cap `LEDGER_TAPE_BARS_MAX`). The day picker gains "10d" (`LEDGER_SPAN_SESSIONS_LONG` 10 —
  MINE, HIS CALL Q3); the default span stays 5d. Contracts: `scripts/contracts.mjs` "🕰️ Gajjala entry tape + replay
  (2026-10-16)". ✨ `chart-maps-gajjala-entry-timeline-2026-10-16`. Doc + HIS CALL Q1–Q10:
  `docs/gajjala/entry_timeline_2026_10_16.md`.
- **⏪ Replayed line** (2026-10-16, Ajay: *"build a pre historic timeline or so?"*). **Not a backtest, not a
  measurement — these never rang.** 2026-10-09 and 2026-10-12 (the sessions before the tab kept records) replayed by the
  offline `backend/scripts/gajjala_replay.py` (`--sessions --cache --out [--write --sha] [--offline] [--types]`; today's
  detectors on the study cache's as-printed minutes, `S.study_symbol_day(…, method="v2")`, A+ only, graded by
  `ledger.grade`; refuses 09:30–16:00 ET and any session with a `gajjala_alerts` / `gajjala_scan` doc) into the NEW
  `gajjala_replay` collection (`store.REPLAY`, `upsert_replay` — `REPLAY:{date}|{SYM}|{setup}` ids only,
  `REPLAY_KEYS`). The 🏁 ledger reads them as a third line (`LINES[2]` "replayed", Kind "⏪ A+ replayed", chip
  `REPLAY_CHIP` / `REPLAY_CHIP_UNGATED` on 🎾), own count bucket `counts["replayed"]` with `pct` always None, served
  `replayed_text` / `replayed_note` (`REPLAY_NOTE`); never in a live / shadow / 🎯 count or any %; the nightly
  `grade_step` never reads or re-grades them (`rows_for(…, with_replay=False)`). The tape of a replayed row = its stored
  `bars5`, never a loader. What a replay cannot know: `ledger.REPLAY_CAVEATS` (served on every doc). Doc (CLI, refusals,
  caveats, run log): `docs/gajjala/entry_timeline_2026_10_16.md` "⏪ Replayed line".
- **✅ / ❌ categories + loss facts** (2026-10-16, Ajay: *"I want winners and losers category in his track record and
  would like us to study the losers"*). Every 🏁 row serves `bucket` (`ledger.BUCKETS` win · loss · open · flat · out,
  `bucket_of` — the later decided column, AMENDMENTS11 F7) and `bucket_text`; the block serves `categories` /
  `categories_timeline` (`CATEGORY_LABELS`, the ROW count inside the served text, replayed rows counted apart " +r ⏪")
  and `category_param` `cat` (FE-only filter in both views, `?cat=loss`). **Rows, never a %** — the count lines and the
  % are unchanged (HONESTY says so). Every loser serves `loss_text` (`ledger.loss_text` — `LOSS_FACT_*` words from the
  stored grade fields only, no regrade, no causal word; thresholds `LEDGER_LOSS_*` MINE). The losers study
  `backend/scripts/gajjala_losers.py` (`--from-json | --mongo`, `--out`, `[--include-replayed]`; imports
  `LG.bucket_of` / `LG.loss_facts`, reads only) lists every loser in pre-declared classes C1–C10 counted on TRADES;
  ≥ `LEDGER_LOSS_CLASS_FLAG_N` (3, his Rule #9) → "candidate rule — HIS CALL"; no win rate, no expectancy, no verdict.
  Docs: `docs/gajjala/entry_timeline_2026_10_16.md` "✅ / ❌ categories and loss facts" (+ HIS CALL Q11–Q17),
  `docs/gajjala/losers_study_2026_10_16.md`.

### Chart Maps — 🎢 High Beta tab — `chart_maps/high_beta_tab.py` (2026-10-14)
Every High-Beta stock and today's move (Ajay: *"Can you create a new tab for High Beta stocks"*, *"Can you please make
sure you do a full scan."*, *"in the High Beta tab.I wanna able to sort my most volatile stocks"*). **UNMEASURED** —
nothing here gates a scan, sizes a position or enters a lane; it is read by the two tape kinds'
watch lists (🎢 watches it, 🗺️ subtracts it) and the Chart Maps membership snapshot (the ✨ arrivals "also on" links). Tab key
`TAB_KEY` "high_beta", label `TAB_LABEL` "🎢 High Beta", slot right after 🔻 Down 10%+. Every number is a named
constant, imported, never retyped; **Ajay** = his 2026-10-14 answers (DECISIONS K1–K4, K3a), **MINE** = AMENDMENTS §8.
- **Universe**: `full` ∪ the Nasdaq-100 (`universe.fetch_nasdaq100()`, Wikipedia; [] or an exception → no QQQ badge, the
  `qqq` box OFF with the reason, passes no name). ETFs (`INCLUDE_ETFS` = `drop10_tab.INCLUDE_ETFS` False) and delisted
  names counted, never rated. NBIS + IREN sit in the static layers of `full` (test-pinned).
- **β**: the house `sepa/beta.py` (cov/var of daily log returns vs SPY over `BETA_LOOKBACK` 252) through the pure
  `beta.beta_from_frame`, bars strictly before the session; β None → `short_history`, counted, never listed. 🛡️ keeps
  its own β (his call to unify).
- **Categories** (Ajay K1 "give me all 3 categories"; the list = the union, each name badged): `B15_MIN` 1.5, `B20_MIN`
  2.0, `TOP_PCT` 20 (ceil of the rated count, ties at the cut included — MINE). Boxes `FILTER_KEYS` b15 · b20 · top20 ·
  qqq · d5 (`DOWN_CHIP_PCT` 5, Ajay K2), the Dual Momentum chip pattern: ANY by default, `hb_mode=all` = must match all.
- **Today's move**: the 🔻 clock (`drop10_tab.mode_for`: live / after_close / closed); prior close = 🛡️'s
  `official_prev_close` (snapshot `prev_day_close` within `drop10_tab.PREV_CLOSE_TOL_PCT` 1% of the cached close);
  held out (`suspect`) beyond it or on the price layer's `GLITCH_RATIO` 5× guard; `no_print` / `no_snapshot` / `stale`
  are never a zero move.
- **View** (AMENDMENTS A1): `rows` = a compact row for EVERY listed name (dense table) + `tiles` for the top
  `board.LIMIT_MAX` 80; default = the names red today, `hb_all=1` includes green (sorted after red).
  2026-10-14 b (Ajay: *"Can you add sort function on the headers and also 5 day and 21 days columns to show how they
  were reacting in price like hot sectors and also add sales tab make it like hot sector with some important metrics
  like EPS, QUAlity and other colums that show the strength of the stock"*; K1): a **Price | Sales** switch above the
  table — `?hb_view=sales` (`TABLE_VIEW_PARAM`), FE-ONLY URL state, never sent to the server, no refetch; the same
  names and the same `hb_all` switch in both. The server serves both column sets every time: `table.columns` =
  `TABLE_COLUMNS` (Symbol, 🔗, Today, 5 days, 5 days vs RSP, 21 days, 21 days vs RSP, β, β × drop, σ, 🎢, QQQ),
  `table.sales_columns` = `SALES_COLUMNS` (Symbol, 🔗, Today, the six 🔥 columns, RS vs SPY (63d)), each column
  `{key, label, title, sort, first}`, plus `table.views` / `table.view_param`. The table never sorts rows itself.
- **Liquidity floor** (Ajay 2026-10-14, the Liquidity menu screenshot: *"Give me all option and default to all in this
  please"*): the tab opens with **No floor** — `board.TAB_DEFAULT_MIN_TIER = {"high_beta": "any"}`, resolved by
  `board.default_min_tier(tab)` in `board()`, the API (`min_tier` omitted) and the FE (`defaultMinTier(tab)`); the four
  options stay in the menu, an explicit `min_tier` applies, every other tab keeps `DEFAULT_MIN_TIER` "ok".
  `membership.is_default_request`: the tab's own default (or None) = the default request; a chosen floor writes nothing.
- **Orders** (served, tab-scoped, `TAB_SORTS`): `hb_swing` 🎢 β × today's drop (the default — MINE, his "you pick"),
  `hb_drop` 📉 today's drop, `hb_vol` 🌊 most volatile first by σ (`SIGMA_BARS` = `resiliency_tab.VOL_AVG_BARS` 50 daily %
  returns, Ajay K3a — window his open call). `default` and any other key → `hb_swing`.
  **Header sorts (2026-10-14 b, K4):** every column of both views sorts on a header tap — first tap = the column's
  first direction, tap again flips. `HEADER_SORTS` (sort key → column, first direction) is the ONE table;
  `TAB_SORTS = tuple(HEADER_SORTS)` with the three presets first (they stay and become their columns' sorts: β × drop
  desc, Today asc, σ desc). New param `hb_dir` (`DIR_PARAM`, `asc`|`desc`; absent / blank / junk → the column's first
  direction, never a 4xx). A preset in its own first direction runs the old `sort_key` verbatim (golden-tested);
  every other (key, direction) runs 🔥 Hottest's engine (`HOT._sorter` + `HOT._rank_names`: missing LAST both ways,
  exact ties A→Z). First directions: Today asc, Symbol A→Z, Next ER soonest first, every other column highest first
  (🔗 by the number of tagged funds, AMENDMENTS2 B3). The top-80 chart cards follow the active sort (the server
  order). Served on the block: `sort_dir`, `sort_preset` (the preset key iff the active order is one, else null) and
  the order line naming the column and how it runs. `out["sorts"]` stays the three presets; the generic Sort select
  is hidden on 🎢 (his call).
- **5 / 21 days** (2026-10-14 b, K2 "Both (4 columns)"): the stock's own `LEG_FAST` 5 / `LEG_SHORT` 21-session %
  move (= `rotation/tracker.py` `WINDOW_FAST` / `WINDOW_SHORT`, via `RT.trailing_return`, rounded 2 dp like
  `member_stats`) AND the same minus RSP's (`RT.traction_row`, percentage points; SPY when RSP has no read — the
  tracker's `BENCHMARK_FALLBACK` rule; blank when neither — a raw move never lands in a vs column). Closed bars:
  the windows END at the last CLOSED session — live = through the prior close (today stays in Today), after-close /
  closed = the session's own close. Each listed name keeps its last `TAIL_BARS` 64 closes from the frames the base
  already reads (zero new fetch). SPY's and RSP's own 5 / 21 print once in `returns_line`. Cells print
  `LEG_TEXT_DP` 1 decimal like 🔥 Hottest (AMENDMENTS2 B8); the sort reads the 2-dp number. DISPLAY only.
- **Sales view** (2026-10-14 b, K1 + K3): the 🔥 Hottest fundamentals columns — Sales YoY, Sales trend, Q EPS, Margin,
  Quality ⓘ, Next ER — through Hottest's own functions, never a second formula: ONE `HOT._decision_map` + ONE
  `HOT._earnings_map` over the listed names, rows via `HOT._fundamentals_row` (served `rows[].fund` = exactly
  `FUND_ROW_KEYS`), ⓘ via `HOT._quality_info` (served as a copy, `group_rows` None), memoised `FUND_TTL_SEC`
  (= `BASE_TTL_SEC`, MINE) in `_fund_memo`, read by `build()` AFTER `_base_for` (the base build does not grow). A
  failed / empty read is never memoised: `fundamentals.state = "not_read"`, the Sales cells blank, never zero. The
  FE draws each cell with 🔥's own `HsFundCell` (exported from `HottestSectors.tsx`). Plus **RS vs SPY (63d)**
  (K3): the `RS_WINDOW` 63-session move (= `tracker.WINDOW_MED`) minus SPY's to the same close, in percentage
  points — not a ratio or a percentile. **UNMEASURED** on this tab (`FUND_NOTE`): nothing ranks, gates, sizes or
  alerts on Sales, EPS, margin, Quality or RS.
- **Memo**: the 🔻 pattern (memo + warm thread, `LIVE_TTL_SEC` / `CLOSED_TTL_SEC` / `BASE_TTL_SEC`, `FAIL_RETRY_SEC`); one
  `bulk_cached_frames` per session, one snapshot fan-out over the listed names; no cron, no Mongo store, nothing scans on
  the request.
- **Endpoints**: `GET /chart-maps?tab=high_beta[&sort=hb_swing|hb_drop|hb_vol|<any HEADER_SORTS key>][&hb_dir=asc|desc][&hb=][&hb_mode=][&hb_all=1]` (block `high_beta_board`; `hb_view` is FE-only) and
  `GET /chart-maps/high-beta/watch` (the 🎢 tape-burst watch list, biggest drop first, the house `safety_floor.MIN_SHARE_PRICE` $2 floor, uncapped).
  ℹ️ panel: `rules_info` section "high_beta" (before "gajjala"), built from the constants.
- **Study** ("look at historically"): `scripts/high_beta_study.py`, prereg
  `docs/research/high_beta_2026_10_14_prereg.md`, literal `high_beta_measured.py` (`{"state": "unmeasured"}` until pasted).
  Status today: NOT RUN. Its verdict changes only the served study line.
- **Tape bursts** (Ajay: *"I need a tape burst notification specific for High Beta stocks from the reselinet separately
  and also other tape bursts from the Chart Maps page"*): `orderflow/tape_burst_kinds.py`, kinds `tape_burst_highbeta`
  (the tab's names, `HIGHBETA_MAX_SYMBOLS` 150) and `tape_burst_chartmaps` (every Chart Maps tab's served names minus
  ⚡ zone names and the 🎢 list, round-robin, `CHARTMAPS_MAX_SYMBOLS` 150). Owner-only, LIVE, ON for him
  (`OWNER_KEEP_SET`); the `tape.BURST_*` rule; location-free; `trade_flash.WATCH_OPEN_ET`–`WATCH_CLOSE_ET` every 5 min;
  a High-Beta name's burst rings as 🎢 even at a zone; one `_id` = one /alerts row (`tape_burst_events` ↔
  `trade_flash_events`). UNMEASURED.
- **Docs**: `docs/chart_maps/high_beta_tab_2026_10_14.md`, `docs/alerts/tape_burst_kinds_2026_10_14.md`.

### Tape — 🎚️ buyers in control on pinned names — orderflow/tape_control.py (2026-10-16)
Ajay 2026-10-16, two messages: *"Can you add a watcher tape for IREN please."* then *"I wwant you to alert me when the
Buyers are winning in tape for IREN today."* One owner-only LIVE push kind `tape_control` (🎚️, `MARK`). LIVE since
12:19 ET 2026-10-16 (main `b2a0604b`). **UNMEASURED** — no study measures this check alone; the Tape verdict's forward
ledger (`GET /orderflow/ledger/accuracy`) grades the five-check verdict, not check 3 (`UNMEASURED_NOTE`). Not advice.
- **The rule = the Tape tab's check 3, BY CALL**: `signals.delta_check` over `tape.analyze_tape(trades)["delta"]` — the
  session's cumulative delta `> 0` AND the last `tape.LATE_WINDOW_MIN` (30) minutes' delta `>= 0`, REGULAR prints only
  (`tape.split_by_kind(...)["flow"]`), pre-market counted (the pull is the ET day 04:00–20:00). No quotes are passed, so
  sides are the **tick rule** (`RULE_WORD`); the Tape tab classifies against the NBBO where it can, so the two reads can
  differ — every push ends with `RULE_TAIL` "tick rule (the Tape tab's quote-rule read can differ)". No new tape math, no
  new provider. One `tape.fetch_trades(sym, day, max_429=MAX_429)` per active pin per poll (`MAX_429 = 3  # MINE`; the
  default `max_429=None` keeps every other caller unchanged). "Today" = the ET day of the poll clock, never the container's.
- **WATCH** = `{"IREN": "2026-10-16"}  # Ajay 2026-10-16` — symbol → the LAST session (inclusive) it is read and rings;
  `None` = standing. An expired pin is never fetched; when no pin is active the pass records `REASON_NO_PIN`.
- **Where it runs**: the EXISTING `2-57/5 9-15 * * 1-5 … sepa.cli trade-flash-watch` line (no crontab line of its own).
  `sepa/cli.py` calls `tape_control.run_pass` AFTER `trade_flash.run_watch` and its heartbeats, in its own try
  (AMENDMENTS7 A1 — `trade_flash.py` is not edited; a fault here never touches the zone or burst passes), and beats
  `engine_heartbeat` `tape_control` only when the pass returns `ran: True` (`ran` = no active pin, or ≥ 1 good read —
  A5). `--kinds` selects it (`tape_control.selected`); `--dry-run` reads and writes nothing. `run_pass` self-gates on
  `trade_flash.in_window` (09:32–16:00 ET); `MARKET_ALERT_KINDS` keeps it silent on closed days. No tape read STARTS
  later than `START_BY_SEC` (= `tape_burst_kinds.KINDS_BUDGET_SEC`, 200 s) into the poll (a `budget` fault, `skipped_budget`).
- **State machine** — pure `decide(prev_state, read)`; a read fault (None: `FAULT_WORDS` no_prints / no_regular /
  truncated / rate_limited / error / budget / no_mongo) is never a False:

  | prev `in_control` | read | ring | after |
  |---|---|---|---|
  | none (no doc today) / None (faults only) | fault | no | unchanged, `faults` +1 |
  | none / None | True | **YES** — the day's first read rings; W2 ends " · first read today" (A6) | in control, `since` = the read |
  | none / None | False | no | not in control (armed) |
  | False (armed) | True | **YES** (the flip) | in control, `since` = the read |
  | False | False / fault | no | unchanged (a fault never re-arms twice) |
  | True (holding) | True | **no** — except the A3 retry: the last ring reached no device and `push_attempts < MAX_PUSH_ATTEMPTS` (2, MINE) | holding |
  | True | False | no — RE-ARM; delivery bookkeeping reset | not in control |
  | True | fault | **no, and NOT re-armed** | holding, `faults` +1 |

  A3: the state is CLAIMED before the send (optimistic `rev`; a lost claim = `lost_race`, no ring; a `DuplicateKeyError`
  on the first upsert = `lost_race`, A9) and PATCHED after it with the outcome: `sent ≥ 1` → `rang`; else
  `push_attempts` +1, `not_pushed_reason` ∈ no_device / not_sent / no_mongo / insert_failed / error
  (`NOT_PUSHED_WORDS`); at the cap `exhausted` and the /alerts text says "rang twice to no device — check Notifications".
- **Collections**: `tape_control_state` (`STATE_COLL`, `_id` `SYM:day`, one doc per pin per ET day: `rev`, `in_control`,
  `since`, `last_read`, `faults`, `last_fault`, `rings[]`, `rang`, `push_attempts`, `not_pushed_reason`, `exhausted`,
  `first_read`); `tape_control_events` (`EVENTS_COLL`, its own — a `trade_flash.event_id` ring id can collide with a
  burst window second in `tape_burst_events`); one ring = one event through `trade_flash.record_and_push` →
  `sender.send_to_user(owner)`; `alert_pass_latest` `_id "tape_control"` (`COUNT_KEYS`).
- **/alerts row**: `GET /alerts/status` → `passes.tape_control` = the pass counts + `cadence_sec` 300 + `window` +
  `pins[]` (`symbol`, `date`, `until`, `active`, `state` waiting / no_read / in_control / not_in_control / expired, served
  `text`, `url` `/sepa/{SYM}?tab=tape&from=alerts`, `rang`) + `note` (`alert_status.read_tape_control` →
  `tape_control.status_block`; `alert_status` stays a leaf — lazy import). The page draws a 🎚️ row
  (`TAPE_CONTROL_PASS`, `data-testid="tape-control"`) under the 🎢 🗺️ TAPE strip, judged inside the served window, NOT
  one of the intraday `PASSES`; it prints each of today's pins' `text` and the `note` verbatim and composes no pin
  sentence. Push tap → `/sepa/IREN?tab=tape&from=alerts` (`push/recent.ITEM_URL_BY_KIND`).
- **Keep-set**: in `push/subs.OWNER_KEEP_SET` (owner-only, LIVE), `default_prefs` False for everyone; his 4 devices
  flipped `None → True` by `scripts.owner_prefs_apply --apply` at deploy (authorised by "alert me"). ℹ️ rules line
  `rules_info._tape_control_lines` (the 🔔 section's alerts list), built from the constants; Notifications toggle;
  `health_audit.check_tape_control_heartbeat`.
- **HIS CALLS** Q1–Q13 (tick vs quote rule, the definition, the edges, when it rings, the window, expiry, sellers taking
  over, an editable pin list, thin tape, a ring that reached no device, the start guard, the tap, the first read):
  `docs/alerts/tape_control_2026_10_16.md`. Each ships with its default.
- **Docs**: `docs/alerts/tape_control_2026_10_16.md`.

### Chart Maps — 🕯️ Doji Sweep tab — `chart_maps/doji_sweep_tab.py` (2026-10-16)
A doji after a test of the prior low, in a downtrend (Ajay: *"create me a new tab for Doji candle after a sweep. For any
stocks after a down trend. May be from all chart maps especially on the 60% 70% down stocks"*). **MEASURED 2026-10-16** (one pre-registered outcome run — `scripts/doji_sweep_study.py`, prereg
`docs/research/doji_sweep_study_2026_10_16.md`, artifact `scripts/doji_sweep_measured.json`, results
`docs/research/doji_sweep_study_2026_10_16_results.md`): primary no_signal, the control no_signal, the any-read cell's
two bootstrap axes disagree — no edge; the served
line changes only through `chart_maps/doji_sweep_measured.py`. Tab key `TAB_KEY` "doji_sweep", label `TAB_LABEL` "🕯️ Doji
Sweep", slot right after 🚩 Gajjala's (Chart Maps tab order: … 🎢 High Beta · 🚩 Gajjala's · 🕯️ Doji Sweep · 〰️ 9 EMA ·
W/M …; `board.TABS` appends it last); block `doji_sweep_board`; a memo tab (`membership.MEMO_BLOCK_KEY`).
- **Engine**: ONE pure `frame_features()` + `row_statuses()` — the tab reads the last closed bar (`KL.closed_frame`, the
  20:00 ET roll), the study every bar. Fires on: a doji (body < `DOJI_BODY_PCT` = `scalping/candles.DOJI_BODY_PCT`, strict);
  the low within `SWEEP_TEST_PCT` (Ajay) either side of the lowest low of the prior `SWEEP_REF_SESSIONS` sessions, that low
  ≥ `SWEEP_REF_MIN_AGE` sessions old (Turtle Soup, Connors & Raschke 1995); ANY read — ≥ `DOWN_PCT` under the 52-week high
  (📉 `fallen_tab.closed_read`), ≥ `DOWN_PCT` under the all-time high (🏔️ `ath_tab.closed_read`), close below the
  `SMA_FAST`- and `SMA_SLOW`-day SMAs.
- **Board**: ONE `bulk_cached_frames` find + ONE `ath_history.read_many` + ONE `ipo_age.listing_dates_map` in a memo thread
  (first answer warming; `MEMO_TTL_SEC`); the request path = the body switch (`dj_body` 5 | 10), the chips (`dj`, every ticked
  chip must pass: 52-week 40 / 60 / 70, all-time 60, below the averages, undercut and reclaimed), three orders (`default`,
  `doji_test`, `doji_ath`), the house "ok" floor; ONE `_bulk_snaps` + ONE zone read over the shown pool. Writes nothing.
  The card charts go through the board's shared `_attach_bars → prices.load_prices` path every board tab uses (AMENDMENTS6
  B10). Counted, never listed: ETFs, delisted, stale bars, < `YEAR_BARS` sessions, scale glitches (named).
- **No push**: `orderflow/tape_burst_kinds.EXCLUDED_TABS = ("doji_sweep",)` — the tab's names never ride the 🗺️
  `tape_burst_chartmaps` watch (AMENDMENTS6 B3; his call Q15 to turn it on). No alert kind, no crontab change.
- **Ledger**: the 17:20 `python -m patterns.history` run records every fired candle of the last `LEDGER_BACKFILL_SESSIONS`
  closed sessions (`record_doji_sweeps`, kind `doji_sweep`, read `bullish_reversal_setup`, graded on the next
  `CANDLE_HORIZON` sessions), after the existing kinds; `GET /patterns/accuracy` serves it under its own `doji_sweep` key
  (headline = the 5% body at or above the floor; `doji_sweep_10pct` and `doji_sweep_thin` sub-blocks, never pooled), never
  the 📐 page's candles.
- **Study**: point-in-time over the `full` universe's cached bars with the same engine; matched placebo (same name, same
  read set, k = 5, never inside an outcome window); every outcome also net of SPY over the same sessions; CIs by
  `BLOCK_SESSIONS`-session date block (binding) and by name — a verdict word only when both agree; verdicts for exactly
  three pre-registered cells (≥ 60% under the 52-week high · any read · a test without a doji), Holm-corrected; every other
  cell exploratory, the ≥ 70% cell pre-declared too small; `--no-fetch` only, Mongo read-only; survivors-only.
- **Docs**: `docs/chart_maps/doji_sweep_tab_2026_10_16.md`, `docs/research/doji_sweep_study_2026_10_16.md`.

### Chart Maps — 🔴 live today candle + now line on every card — chart_maps/live_card.py (2026-10-16)
Every Chart Maps card's today candle and its dashed now line follow the last print (Ajay, three messages: *"Can you make
this chart more live please like when its 24 hour or todays entry"*, his XLAB screenshot pair — the card's "now 2.64"
against the ticker page's "$2.77 … Today · Live" — and *"actual price is this  above but it stale value"*). Display
only: scans, bands, the ledger and the 📐 page still read closed bars (the live-bar overlay trap).
- **Endpoint**: `POST /chart-maps/live` body `{"symbols": [...]}` (`chart_maps/api.py` → `live_card.compose`, run in a
  thread). ONE `prices.bulk_snapshot` + ONE `prices.bulk_cached_frames` (a Mongo find, never a fetch). Per symbol the
  card's last bar is built BY CALL through the board's own chain — `prices.with_today_bar` → `board._norm_frame` →
  `board._frame_to_bars` → `board._tag_live_bar` (`s: "pre"|"ah"` kept) — and the now block by calling
  `board.attach_live_now` on a probe tile (`board.now_label`: "now" / "now · pre" / "now · AH"). In RTH the candle closes
  at the last trade, high/low widened to it (`CLOSE_FOLLOWS_PRINT_RTH`, a print of another day or session never touches
  the bar). Answer keys: `session` (`zone_edge.session_state`), `as_of`, `footer {live, stale}`, `now_labels`, `cap`,
  `asked`, `served`, `missing`, `fault`, `faults`, `quotes {SYM: {bar, prev_t, prev_bar, now}}`. One symbol that fails is
  omitted with a served word (AMENDMENTS8 C2); a snapshot that answers nothing — or every asked symbol faulted — is
  `fault` with `footer {live: null, stale: null}` (a read that served nothing claims no "live · …" time).
- **Cap**: `live_card.cap()` = `prices._SNAP_CHUNK` by name (one snapshot call); above it the read is refused whole —
  413 "up to {cap} symbols per live read — {n} sent", never a partial cut; a non-list body → 422. `board.LIMIT_MAX` ≤ the
  cap, so the FE never splits.
- **Nothing written**: no cache writer is imported or called (pytest source guard + writers monkeypatched to raise);
  `with_today_bar` returns a copy; no auth beyond the house proxy (read-only).
- **FE cadence** (`hooks/useCardLive.ts`, constants in `lib/cardLive.ts`): `CARD_LIVE_MS` (= `SessionPrice`'s poll, MINE)
  while the tab is visible; `CARD_LIVE_CLOSED_MS` (= `drop10_tab.CLOSED_TTL_SEC`, Cheetah default) when the session is
  closed. C1: the pacing session is the BOARD's `tape_session` first, then the last good answer. C3: one tick right after
  every board refetch (the refetch wins for one tick, then the overlay re-applies at once) — except while closed, where
  the rest of the closed cadence since the last POST is waited out. `document.hidden` → no POST; none while one is in
  flight; back to visible after more than a cadence → one POST at once; unmount aborts and drops an in-flight answer. The
  5-minute `BOARD_REFRESH_MS` refetch is unchanged (bands, chips, order).
- **Patch rule** (`lib/cardLive.patchTile`, the FE composes no word): a served bar with the tile's last date replaces the
  last bar; a newer served bar whose `prev_t` is the tile's last date is appended (never a slide — curves and `vol_avg`
  are index-aligned), and the served `prev_bar` (a closed bar, no `s` tag — C4) replaces the tile's last bar first; an
  older bar, a tile ending on another session (a Winners window) or an intraday tile → bars unchanged. Tone-`now` lines
  take the served price and, when their label is one of `now_labels`, the served label (custom wording kept); a tile with
  no now line gains one only when `add_line`. Unchanged → the same tile object (PatternChart `memo`). The served footer
  word joins the existing `cm-scanstamp` freshness line ("live · HH:MM:SS ET" / "last refresh HH:MM ET") — no new chrome.
- **Budget**: one Massive snapshot call + one Mongo find per 30 s per open, visible board tab (≤ the cap); one per 30 min
  closed. No WS, no SSE, no focus-list change.
- **Contracts**: `scripts/contracts.mjs` "🔴 live card overlay (2026-10-16)". **Tests**:
  `backend/tests/test_chart_maps_live_card.py`, `frontend/src/lib/cardLive.test.ts`, `src/hooks/useCardLive.test.tsx`,
  `src/pages/ChartMapsCardLive.test.tsx`, `src/components/PatternChart.cardLive.test.tsx`.
- **HIS CALLS**: `docs/chart_maps/live_card_2026_10_16.md` (Q1–Q14 + the builders' a–d).

---

## 4. Live Data Layer

### Finnhub WebSocket subscription model
- `tracked_symbols: set[str]` — authoritative list of subscribed tickers.
- `_ws_subscribe_queue: asyncio.Queue[str]` — pump for new subs while WS is open.
- `subscribe_symbols(symbols)` — idempotent; dedups against `tracked_symbols`,
  enqueues each new symbol, fires a one-shot `_rest_fetch_once(sym)` so SSE
  has data immediately.
- `finnhub_ws_consumer()`:
  - Connects `wss://ws.finnhub.io?token={KEY}` with `ping_interval=20`.
  - On reconnect, re-subscribes everything in `tracked_symbols`.
  - Inner `pump_subs` task drains `_ws_subscribe_queue` (re-queues on send fail).
  - Trade frames → `cache.update(symbol, {price, volume, source: finnhub_ws,
    trade_ts})`.
  - Backoff: 2s → ×2 → cap 60s.

### REST poller (`finnhub_rest_poller`)
Every `POLL_INTERVAL_SEC` (default 5s), calls `/api/v1/quote` for each tracked
symbol, fills in `{open, high, low, prev_close, pct_change}`. Preserves
`source` if the WS already wrote.

### yfinance polling
- `prices.load_prices` is the only yfinance consumer; cached parquet (TTL 20h)
  under `~/.cheetah/prices/`.
- `indian_market.fetch_indian_market` and `news.py` use raw HTTP to Yahoo
  endpoints (NOT yfinance lib).

### Caching
| Store | Path / Key | TTL | Writer |
|---|---|---|---|
| Mongo OHLCV (primary) | `cheetah.price_cache` (one doc per symbol) | 20 h | `prices.load_prices` |
| Parquet OHLCV (fallback) | `~/.cheetah/prices/{SYM}.parquet` | 20 h | `prices.load_prices` |
| Mongo scan history | `cheetah.scan_runs` + `cheetah.candidate_snapshots` | persistent | `history.write_scan` |
| Latest scan | `~/.cheetah/scans/latest.json` | manual | `scanner.scan_universe` |
| Morning brief | `~/.cheetah/scans/brief.json` | manual | `brief.generate_brief` |
| Watchlist | `~/.cheetah/scans/watchlist.json` | manual | `scanner.add/remove_to_watchlist` |
| News (US) | in-mem `news._cache[symbol]` | 180 s | `news.fetch_news` |
| News (IN) | `news._cache["__IN_*__"]` | 180 s | `news.indian_news` |
| News (mkt) | `news._cache["__MARKET__"]` | 180 s | `news.market_news` |
| Indian quotes | `indian_market._quote_cache["__all__"]` | 30 s | `fetch_indian_market` |
| Tick window | `cache._ticks[sym]` deque | maxlen=64 | `QuoteCache.update` |

---

## 5. Frontend (React + Vite + TypeScript)

### Routes (`App.tsx`)
| Path | Component |
|---|---|
| `/` | redirect → `/dashboard` |
| `/dashboard` | `ModernDashboard` |
| `/india` | `IndianMarket` |
| `/live` | `LiveStream` |
| `/sepa` | `SepaPage` |
| `*` | redirect → `/dashboard` |

`main.tsx` wraps in `<BrowserRouter>` and imports the CSS layers
(`tokens, EnhancedStyles, typography, navbar, dashboard, live, india, polish`).

### Pages

- **`pages/ModernDashboard.tsx`** (`ModernDashboard`): the editorial-style "Cheetah
  Score" landing page. Shows `SepaBriefBanner`, page header with `RefreshButton`,
  the `FormulaCard` + `IndicatorsCard`, `CheetahTable` of Tier-1 picks plus a
  3-column grid (`CompetitorScoutCard`, `UnicornsCard`, `EtfsCard`),
  `EnhancedIndianStockTable` strip, and `NewsPanel`. Data via `useCheetahStocks`.
- **`pages/LiveStream.tsx`** (`LiveStream`): manages a local `symbols` array
  (default `NVDA,META,AAPL,MSFT,TSLA,AMD,PLTR,CRDO`), wires `useMarketStream` for
  SSE quotes and `useCheetahStocks` for a score lookup. Renders `QuoteRow`
  rows, an add-ticker form, status pill (`connecting/open/closed/error`),
  `WatchlistSection`, and `StockDetailModal` on row click.
- **`pages/IndianMarket.tsx`** (`IndianMarket`): `useIndianStocks` (auto-refresh
  60s) → `IndianMarketIndices` strip + `IndianStockTable` + `IndianNewsPanel`.
- **`pages/Sepa.tsx`** (`SepaPage`): SEPA dashboard. `useSepaScan` provides
  `data, scanning, runScan, refetch`. Header shows scan metadata + 3 buttons
  (Reload, Scan Now fast, Scan + catalyst slow). Toggle to show all analyzed.
  Table columns: Symbol, Score, RS, Stage, Trend (n/8), Setup, Pivot, Stop,
  Base #, Vol. Row click opens `SepaCandidateModal`.
- **`pages/Dashboard.tsx`** — apparently the older/shorter dashboard (63 lines);
  `App.tsx` does NOT route to it — **dead route**. See § 9.

### Components (purpose / props)

| Component | Purpose | Key props |
|---|---|---|
| `NavBar` | Top nav with theme toggle, route links, today's date | none |
| `ThemeToggle` | Light/dark switch driven by `useTheme` | none |
| `FormulaCard` | Renders `FORMULA_WEIGHTS` table (static) | none |
| `IndicatorsCard` | Static education panel listing INDICATORS + EXPERTS | none |
| `CheetahTable` | Sortable table over `CheetahStock[]` with score, signals, mcap, etc. | `{stocks}` |
| `CompetitorScoutCard` | Fetches `/competitors`, renders anchor + peers grid | none |
| `UnicornsCard` | Fetches `/unicorns`, renders private-co table | none |
| `EtfsCard` | Fetches `/etfs`, renders thematic ETF list | none |
| `NewsPanel` | Tab over WATCH = `[Market, NVDA, CRDO, PLTR, META, LLY, ALAB, AVGO, MRVL]`, fetches `/news` | none |
| `RefreshButton` | "Rerun formulas" / refresh button + relative timestamp | `{onClick, loading, computedAt}` |
| `IndianStockTable` | Compact NSE/BSE table with INR formatters | `{stocks}` |
| `EnhancedIndianStockTable` | Richer variant used on Modern dashboard | `{stocks}` (currently called with `[]` — uses internal hook? **check**) |
| `IndianMarketIndices` | Indices strip (Nifty/Sensex/etc.) | `{indices}` |
| `IndianNewsPanel` | Tab over [Market, RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, BHARTIARTL, SBIN], hits `/indian-news` | none |
| `Sparkline` | SVG line over last N prices | `{values, width=96, height=28}` |
| `QuoteRow` | A row of LiveStream table — formats price/RSI/VWAP, sparkline, cheetah score | `{quote, cheetahScore, onRemove, onSelect}` |
| `WatchlistSection` | Filter UI by tier (Hypersonic/Cheetah/Fast Mover/Strong Gainer) + sector | `{onSelect}` |
| `StockDetailModal` | Modal w/ symbol metadata from `data/watchlist.ts` | `{symbol, meta, onClose}` |
| `SepaBriefBanner` | Top banner showing latest brief summary; calls `useSepaBrief` | none |
| `SepaCandidateModal` | Deep-dive modal — fetches `/sepa/candidate/{sym}`, renders trend + catalyst + insider | `{symbol, onClose}` |

### Hooks (`src/hooks/*`)
| Hook | Returns | Endpoints |
|---|---|---|
| `useMarketStream(symbols)` | `{quotes: Record<sym, Quote>, status}` | `EventSource('/stream?symbols=...')` |
| `useCheetahStocks()` | `{stocks, weights, computedAt, error, loading, refetch}` | `GET /cheetah` |
| `useIndianStocks()` | `{stocks, indices, fetchedAt, loading, error, refetch}` | `GET /indian-stocks` (60s interval) |
| `useJsonApi<T>(url)` | `{data, error, loading, refetch}` | generic GET |
| `useSepaScan()` | `{data, loading, error, scanning, refetch, runScan(noCatalyst)}` | `GET POST /sepa/scan` |
| `useSepaBrief()` | `{data, loading, regenerating, regenerate, refetch}` | `GET POST /sepa/brief` |
| `fetchSepaCandidate(sym)` | promise | `GET /sepa/candidate/{sym}` |
| `sepaRescan(sym)` | promise | `POST /sepa/rescan/{sym}` |
| `fetchWatchlist / addToWatchlist / removeFromWatchlist` | promise | `/sepa/watchlist*` |
| `planPosition(params)` | promise | `POST /sepa/position-plan` |
| `useTheme()` | `{theme, setTheme, toggleTheme}` | localStorage `cheetah.theme` + `prefers-color-scheme` |

**Note:** `useSepa.ts` hardcodes `const API = 'http://localhost:8000'` rather
than relying on Vite proxy (works in dev, breaks if frontend ever served
elsewhere). Other hooks use relative URLs that *do* go through the proxy
(`vite.config.ts` lists every endpoint except `/sepa/*` — so SEPA only works
because of the hardcoded host).

### API surface used (from frontend)
`/cheetah, /competitors, /unicorns, /etfs, /news, /stream, /indian-stocks,
/indian-news, /sepa/scan, /sepa/brief, /sepa/candidate/:s, /sepa/rescan/:s,
/sepa/watchlist*, /sepa/position-plan, /sepa/notify/test,
/sepa/alerts/price (POST/GET/DELETE), /sepa/alerts/recent, /health (unused?)`.

#### Frontend modules added for alerts
- `src/hooks/usePriceAlerts.ts` — typed API client (`createPriceAlert`,
  `listPriceAlerts`, `deletePriceAlert`, `fetchRecentFires`) plus
  `useAlertNotifier()` hook that polls `/sepa/alerts/recent` every 30s and
  surfaces fires via the browser `Notification` API. Foreground only.
- `src/components/PriceAlertModal.tsx` — drawer-styled modal with kind
  dropdown (`below | above | drop_pct | rise_pct`), level input, channel
  checkboxes (WhatsApp / Browser), optional note. Calls
  `Notification.requestPermission()` on first save when browser is enabled.
- `src/components/SepaCandidateCard.tsx` — adds 🔔 button in the card
  header that opens `PriceAlertModal` (with `e.stopPropagation()` so the
  card click doesn't fire). Modal renders inside a stop-propagation
  wrapper so backdrop clicks don't reopen the candidate detail.
- `src/pages/Sepa.tsx` — invokes `useAlertNotifier()` so the polling loop
  starts on mount.

---

## 6. Scheduled Jobs

### Production: Docker `cron` service (supercronic)

The Mac book pro M5 (this machine) deployment uses the `cron` service in `docker-compose.yml`,
running `supercronic /app/crontab`. Crontab lives at `backend/crontab` and
is bind-mounted read-only into `/app/crontab`. Container TZ = `America/New_York`.

| Schedule | Command | Purpose |
|---|---|---|
| `0 20 * * 0` | `/usr/local/bin/python -m sepa.cli research-refresh` | **Sunday 8pm ET** — heavy weekly research refresh (VCP, Power Play, CANSLIM, liquidity, ADR, IPO age, company name). Pre-warms `sepa_research_cache` for Monday. |
| `30 16 * * 1-5` | `/usr/local/bin/python -m sepa.cli fast-scan` | EOD fast scan (16:30 ET) — joins cached research with today's prices. Typical 20-30s. |
| `30 8  * * 1-5` | `/usr/local/bin/python -m sepa.cli brief` | Morning brief (08:30 ET) |
| `*/5 9-15 * * 1-5` | `/usr/local/bin/python -m sepa.cli alerts` | Position + price alerts during market hours |
| `0,5,10,15,20,25,30 16 * * 1-5` | `/usr/local/bin/python -m sepa.cli alerts` | First half-hour of 16:xx (post-close) |
| `1-56/5 4-20 * * 1-5` | `/usr/local/bin/python -m market_hours.gate chart_maps.gajjala.run` | Gajjala's tab pass (04:01–20:01 ET, trading days) — scanner, closed 5/15-min bars, five detectors, `gajjala_setup` A+ entry push (LIVE since 2026-10-16) + 🧠 gajjala_potential pushes (LIVE). An owner opening the tab may add one on-open pass as an api-spawned subprocess (push gates dry; the cron waits ≤ 45 s for it, never refused). § 3 "Chart Maps — Gajjala's tab". |
| `15 20 * * 1-5` | `/usr/local/bin/python -m market_hours.gate chart_maps.gajjala.nightly` | 20:15 ET — Gajjala float + halt-history + 🎾 squeeze-history warm + 🏁 track-record grade (2026-10-16, last step; same line, no new crontab entry). |
| `2-57/5 9-15 * * 1-5` | `/usr/local/bin/python -m sepa.cli trade-flash-watch` | ⚡ Trade Flash zone bursts (self-gates `trade_flash.WATCH_OPEN_ET`–`WATCH_CLOSE_ET`, 09:32–16:00 ET), then — same line, same process, since 2026-10-14 — the 🎢 `tape_burst_highbeta` and 🗺️ `tape_burst_chartmaps` kinds (`--kinds`, `--dry-run`), and 🎚️ `tape_control` (2026-10-16). No new line: the kinds ride this one; deploy `cron` to carry their code. § 3 "Chart Maps — 🎢 High Beta tab", § 3 "Tape — 🎚️ buyers in control on pinned names". |

**Two operational gotchas (load-bearing):**
1. The crontab MUST use the absolute python path (`/usr/local/bin/python`).
   Bare `python` fails under supercronic with `Failed to fork exec`.
2. The cron service sets `init: true` so Docker's tini is PID 1. On Apple
   Silicon (the production host), supercronic-as-PID-1 fails to re-exec
   itself as a subreaper child — tini sidesteps the path entirely.

### Legacy: launchd (local dev)

| Plist | Schedule | Command |
|---|---|---|
| `com.cheetah.sepa.scan.plist` | Mon-Fri 17:00 | `.venv/bin/python -m sepa.cli scan` |
| `com.cheetah.sepa.brief.plist` | Mon-Fri 08:30 | `.venv/bin/python -m sepa.cli brief` |

Still installable via `launchd/README.md` for non-Docker dev environments.

---

## 7. Env Vars / API Keys

| Var | Read by | Purpose | Behavior if missing |
|---|---|---|---|
| `FINNHUB_API_KEY` | `main.py`, `news.py`, `sepa/providers.py`, `sepa/catalyst.py` | WS feed + REST quote + earnings calendar + company news | WS skipped (warn), REST poll skipped, news source 1 returns `[]`, earnings catalyst returns None |
| `DEFAULT_SYMBOLS` | `main.py` | Default watchlist subscribed at boot | defaults to `NVDA,META,AAPL,MSFT,TSLA,AMD,PLTR,CRDO,AVGO,LLY` |
| `POLL_INTERVAL_SEC` | `main.py` | REST poller cadence | 5 |
| `TICK_WINDOW` | `main.py` | Rolling tick deque length per symbol | 64 |
| `NEWS_CACHE_TTL_SEC` | `news.py` | News in-mem cache TTL | 180 |
| `POLYGON_API_KEY` | `sepa/providers.py` | Future polygon routing | flag-only; **no effect today** |
| `SEC_USER_AGENT` | `sepa/insider.py` | EDGAR requires identifying UA | defaults to `"Cheetah Market Research research@cheetah.local"` (works but use your own) |
| `SEPA_UNIVERSE_FILE` | `sepa/universe.py` | Override universe with text file (one ticker/line) | ignored if file missing |
| `SEPA_UNIVERSE` | `sepa/universe.py` | Override universe with CSV | ignored if unset |
| `MASSIVE_API_KEY` | `sepa/prices.py` | Daily bars + real-time last-trade | falls back to yfinance |
| `PRICE_PROVIDER` | `sepa/prices.py` | `massive` (default) or `yfinance` | defaults to massive |
| `MONGO_URL` | `sepa/prices.py`, `sepa/alerts.py`, `sepa/price_alerts.py` | Mongo connection | falls back to parquet / in-memory |
| `MONGO_DB` | same | DB name | `cheetah` |
| `TWILIO_ACCOUNT_SID` | `sepa/notify.py` | Twilio API auth | WhatsApp send returns False with warning |
| `TWILIO_AUTH_TOKEN` | `sepa/notify.py` | Twilio API auth | same |
| `TWILIO_FROM` | `sepa/notify.py` | Sender (`whatsapp:+...`) | defaults to sandbox `whatsapp:+14155238886` |
| `TWILIO_TO` | `sepa/notify.py` | Recipient (`whatsapp:+...`) | WhatsApp send returns False with warning |

`.env.example` ships only `FINNHUB_API_KEY, DEFAULT_SYMBOLS, POLL_INTERVAL_SEC,
TICK_WINDOW`. The current `.env` ships a **live Finnhub key** (visible in
repo — should be rotated).

---

## 7b. Docker Deployment (production)

Production lives on Ajay's M1 Mac book pro M5 (this machine). Docker Compose orchestrates four
services. Repo: `https://github.com/Ajay-Kandakatla/cheetah-trades`.

### Services

| Service | Image | Ports | Notes |
|---|---|---|---|
| `mongo` | `mongo:7` | `127.0.0.1:27017` (loopback only) | persists `mongo-data` named volume |
| `api` | `cheetah-api:latest` (from `backend/Dockerfile`) | `0.0.0.0:8000` | uvicorn |
| `cron` | `cheetah-api:latest` (same image, different command) | — | `init: true`, runs `supercronic /app/crontab` |
| `frontend` | `cheetah-frontend:latest` (from `frontend/Dockerfile`) | `0.0.0.0:5173 → 80` | nginx serves Vite build, reverse-proxies `/api/*` and `/ws` |

### Volumes
- `mongo-data` — Mongo data dir.
- `cheetah-scans` — bind-mounted to `/root/.cheetah` on **both** api and
  cron, so cron-written `latest.json` / `brief.json` are visible to the
  api process. Same volume holds the parquet price cache fallback.

### Build details
- Backend Dockerfile is multi-arch via `dpkg --print-architecture` (no
  reliance on BuildKit's `TARGETARCH` injection). Installs supercronic
  `v0.2.33` from GitHub releases.
- Frontend Dockerfile is multi-stage (Node 20 builder → nginx 1.27
  alpine). Build-time ARG `VITE_API_BASE=/api` so the SPA always talks
  to `same-origin/api/*`.
- nginx config (`frontend/nginx.conf`) proxies `/api/` → `http://api:8000/`
  and `/ws` → `http://api:8000/ws`.

### Twilio env passthrough
The compose file pulls `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
`TWILIO_FROM`, `TWILIO_TO` from the host shell at `up` time
(`${TWILIO_ACCOUNT_SID:-}` syntax) AND from `backend/.env`. Either source
works; if both are set, compose uses the host shell value.

### Deploy commands (on the mini)
```
# first time
git clone https://github.com/Ajay-Kandakatla/cheetah-trades.git
cd cheetah-trades
cp backend/.env.example backend/.env   # then fill in keys
docker compose build
docker compose up -d

# normal update
git pull
docker compose build api          # rebuild only what changed
docker compose up -d --force-recreate api cron
docker compose logs --tail 20 cron
```

### Health checks
- `docker compose ps` — all 4 services should be `Up`.
- `curl http://localhost:8000/health` — api liveness.
- `curl -X POST http://localhost:8000/sepa/notify/test` → `{"sent":true}`
  confirms Twilio.
- `docker compose exec cron /usr/local/bin/python -m sepa.cli alerts` —
  manual run of the alerts pipeline.

---

## 8. Data Flow Diagrams

### Scan flow
```
launchctl (5pm M-F)            POST /sepa/scan
        │                              │
        └────► sepa.cli:scan ◄─────────┘
                    │
                    ▼
             scanner.scan_universe(symbols, with_catalyst, persist=True)
                    │
                    ├── universe.load_universe()  → ~250 tickers
                    │
                    ├── rs_rank.rs_ranks(work)    → {sym: 1-99}
                    │       └── prices.load_prices  (parquet cache, TTL 20h, yfinance)
                    │
                    ├── ThreadPoolExecutor(8) × _analyze_symbol
                    │       ├── prices.load_prices
                    │       ├── trend_template.evaluate
                    │       ├── stage.classify
                    │       ├── volume.analyze
                    │       ├── vcp.detect
                    │       ├── power_play.detect
                    │       ├── base_count.count_bases
                    │       └── sell_signals.evaluate
                    │
                    ├── filter is_candidate, sort by score
                    ├── market_context.market_state()  (SPY+QQQ trend template)
                    │
                    ├── if with_catalyst: asyncio sem=4 over top-20
                    │       ├── catalyst.catalyst_for      (Google news + Finnhub earnings + yfinance)
                    │       └── insider.insider_activity   (SEC EDGAR FTS form 4/13D/13G)
                    │
                    └── write ~/.cheetah/scans/latest.json
                                 │
                                 ▼
                         GET /sepa/scan  →  React useSepaScan  →  SepaPage table
```

### Brief flow
```
launchctl (8:30am M-F)         POST /sepa/brief
        │                              │
        └─► sepa.cli:brief ◄───────────┘
                    │
                    ▼
            brief.generate_brief(with_catalyst=True)
                    │
                    ├── load latest scan + watchlist
                    ├── slim top-5 candidates
                    ├── per watchlist: load price + compute pnl + sell_signals
                    ├── asyncio sem=4 catalyst+insider sweep
                    │       (only retained if earnings / sentiment / cluster-buy / 13D)
                    └── write ~/.cheetah/scans/brief.json
                                 │
                                 ▼
                         GET /sepa/brief  →  useSepaBrief  →  SepaBriefBanner (top of every page that mounts it)
```

### Live stream flow
```
React mount LiveStream
   │
   ├── new EventSource('/stream?symbols=NVDA,META,...')
   │
   ▼
FastAPI /stream
   │
   ├── subscribe_symbols(syms)
   │       ├── tracked_symbols.add(sym)
   │       ├── _ws_subscribe_queue.put(sym)
   │       └── _rest_fetch_once(sym)  (one-shot Finnhub /quote)
   │
   └── sse_event_generator
           │
           └── loop {snapshot diff → yield "event: quote\ndata: ...\n\n"; sleep 1}
                    ▲
                    │
                    │  cache.update() ← (a) finnhub_ws_consumer (trade frames)
                    │                 ← (b) finnhub_rest_poller (every 5s, OHLC)
                    │  cache.update computes RSI(14), VWAP, sparkline[-32]
                    │
React useMarketStream sets quotes[sym] → re-renders QuoteRow
```

---

## 8b. Spec-Driven Development (spec-kit)

The repo is set up for spec-driven feature development via
[GitHub spec-kit](https://github.com/github/spec-kit). Templates and slash
commands are vendored under `.specify/` and `.claude/commands/` because
spec-kit's release pipeline ships empty assets as of v0.8.1; see
`.specify/README.md` for the workflow.

| Slash command | Step in the workflow |
|---|---|
| `/constitution` | Update `.specify/memory/constitution.md` (project principles) |
| `/specify <text>` | Create `specs/NNN-name/spec.md` describing *what* + *why* |
| `/clarify` | Resolve ambiguities before planning |
| `/plan` | Generate `plan.md` with technical design + data model + contracts |
| `/tasks` | Break the plan into a numbered, dependency-ordered task list |
| `/analyze` | Cross-check spec / plan / tasks for consistency |
| `/implement` | Execute the task list |
| `/checklist` | Generate quality / acceptance checklists |

The constitution at `.specify/memory/constitution.md` codifies the
non-negotiable architecture rules: free-tier first, cache-aware data
layers, two-tier scan architecture (research vs hot), graceful
degradation, SPECS.md as the source of truth. New features must respect
it; amendments bump the constitution version + add a SPECS changelog
entry.

---

## 9. Known Gaps / TODOs

1. **Polygon integration not wired.** `providers.has_polygon()` exists, but
   `catalyst.py` always uses Google News + Finnhub + yfinance regardless. The
   "polygon" provider tag in the catalyst response is cosmetic. Per
   `launchd/README.md` "no code changes required" — that's not currently true.
2. **`pages/Dashboard.tsx` is dead code.** `App.tsx` only routes
   `/dashboard → ModernDashboard`. Remove or wire it.
3. **`EnhancedIndianStockTable` is called with `stocks={[]}`** in
   `ModernDashboard` (line 138), so it shows nothing on the dashboard. Either
   call `useIndianStocks` inside or pass real data.
4. **SEPA hooks bypass the Vite proxy** — `useSepa.ts` hardcodes
   `http://localhost:8000`. CORS is whitelisted so it works in dev, but
   `vite.config.ts` proxy entries for `/sepa/*` are missing → inconsistent.
5. **Live Finnhub key checked into `.env`.** Should be rotated; `.env` should
   be gitignored (it's the only file in `backend/` matching that name and
   ships a real key — confirm via `.gitignore`).
6. **`sepa.cli rescan` is a misnomer** — it only force-refreshes the parquet
   cache; it does NOT update `latest.json`. The next full scan would need to
   run for the symbol to reflect.
7. **`yfinance` recommendations / earnings_history APIs are flaky** —
   `_fetch_yfinance_extras` has multiple `try/except` blocks and silently
   degrades. Not a bug per se, but expect missing fields.
8. **No tests.** Zero test files in repo (no `tests/`, no `*test*.py`,
   no `*.test.tsx`).
9. **`GET /health` not consumed by frontend** despite being proxied. Probably
   useful for `useEffect` connection-check; not used today.
10. **SSE generator does not coalesce** — sleeps a full 1s between snapshot
    diffs even if a trade just fired. Latency floor ≈1s on top of WS.

---

## 10. Provenance Map

> The `minervini.pdf` (book *Trade Like a Stock Market Wizard*, Mark Minervini,
> 2013) was NOT opened during this spec pass. Page numbers below are copied
> verbatim from in-code docstrings the original author left, then **flagged**
> as unverified. Treat each as an action item: open the PDF, confirm, or fix.

| Threshold / rule | Source claim (in-code) | Verification status |
|---|---|---|
| Trend Template — 8 criteria (price>MA150&MA200; MA150>MA200; MA200 up ≥1mo; MA50>MA150>MA200; price>MA50; +30% above 52w low; within 25% of 52w high; RS≥70) | Minervini Trend Template, book Ch on Stage 2 entry | UNVERIFIED — needs human check |
| MA200 trending up "≥1 month = pass, ≥5 months preferred" | inline docstring `trend_template.py:50` | UNVERIFIED |
| RS Rank ≥ 70 (preferred ≥ 80) | `scanner.py:8` docstring | UNVERIFIED — IBD canonical, but page not cited |
| RS weights 40/20/20/20 over 3/6/9/12 mo | `rs_rank.py:3` ("Per IBD's formula") | UNVERIFIED — IBD methodology, not Minervini-specific |
| 4-Stage definitions | `stage.py:1` "Ch 4 of the book" | UNVERIFIED — chapter cited, no page |
| Up/down volume ratio ≥ 1.0 = accumulation | `volume.py:1` "Ch 10" | UNVERIFIED |
| Volume dry-up <0.7 (10d / 50d avg) | `volume.py` (no book cite) | UNVERIFIED — likely heuristic |
| High-vol breakout = vol > 1.5×avg50 + close > 21-bar high | `volume.py` (no book cite) | UNVERIFIED — heuristic |
| VCP base 3-65 weeks, 2-6 contractions, depth 10-35%, avoid >60%, final ≤10% | `vcp.py:3` "Ch 10 (p.198-213)" | UNVERIFIED — page range cited, NOT confirmed |
| Power Play — +100% in ≤8wk; consol 3-6wk ≤25%; final ≤10% | `power_play.py:1` "Ch 10 p.254-255" | UNVERIFIED — page cited, NOT confirmed |
| Base count: ≤2 early, ≥4 late-stage | `base_count.py:1` "Ch 11" | UNVERIFIED |
| IPO-age "80% of 1990s winners IPO'd in prior 8 yrs" | `ipo_age.py:3` (no page) | UNVERIFIED |
| Max stop 10%, avg loss 6-7%, min R:R 2:1 (target 3:1), risk per trade 0.5-2% (default 1%), 4-6 positions ideal | `risk.py:1` "Ch 12-13" | UNVERIFIED — chapter cited |
| Move stop to breakeven at 3R | `risk.py:9` | UNVERIFIED |
| Sell signals: largest 1d/1w decline since stage-2 start; below 50MA on >1.3×vol; below 200MA = full exit; +25% in 3wk = climax | `sell_signals.py:1` "Ch 12-13" | UNVERIFIED |
| Market context — apply trend template to SPY+QQQ; ">90% superperformance from corrections" | `market_context.py:1` "Ch 13" | UNVERIFIED |
| Position cap 25% of account | `risk.py:43` parameter default | VERIFIED — book p.312 ("optimal position size should be 25 percent — four stocks divided equally") |
| Composite score weights (+40 trend / +30 RS / +10 stage2 / +5 accum / +15 base / ±5 base#) | `scanner.py:_analyze_symbol` | NOT BOOK-SOURCED — author's heuristic, no provenance claimed |
| Catalyst BULLISH/BEARISH keyword sets | `catalyst.py:30-40` | NOT BOOK-SOURCED — author-curated |
| Form 4 cluster threshold (3+ unique insiders in 30d) | `insider.py:92` | NOT BOOK-SOURCED — common rule of thumb |

**Action item for next engineer:** open `backend/sepa/minervini.pdf`, walk this
table, and replace UNVERIFIED → `(book p.X confirmed)` or `(NOT IN BOOK — internal
heuristic)`. Several thresholds (volume 1.5×, drying-up 0.7, base 15-bar idle, etc.)
are clearly the author's pragmatic implementation choices — those should be
labelled as such, not as Minervini doctrine.
