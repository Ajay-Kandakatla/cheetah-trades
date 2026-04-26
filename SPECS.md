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
| GET | `/snapshot` | — | `{<sym>: Quote}` | — | `cache.snapshot` |
| GET | `/cheetah` | — | `{weights, stocks[], computedAt}` | — | `cheetah_data.with_computed_scores` (recomputes from `FORMULA_WEIGHTS`) |
| GET | `/competitors` | — | `[{anchor, headline, sub, peers[], anchorStock}]` | — | `cheetah_data.get_competitor_groups` |
| GET | `/unicorns` | — | `Unicorn[]` | — | static `cheetah_data.UNICORNS` |
| GET | `/etfs` | — | `Etf[]` | — | static `cheetah_data.ETFS` |
| GET | `/news` | `?symbol=` (optional) | `{symbol, items[], fetchedAt}` | populates `news._cache` | `news.fetch_news` / `news.market_news` |
| GET | `/stream` | `?symbols=CSV` | SSE stream of `event: quote\ndata: {Quote}` | `subscribe_symbols` (adds to `tracked_symbols`, queues WS subs, fires REST one-shot) | `cache.snapshot` loop |
| GET | `/sepa/scan` | — | latest `scan` payload or `{candidates:[], message}` | reads `~/.cheetah/scans/latest.json` | `sepa.scanner.load_latest` |
| POST | `/sepa/scan` | `?no_catalyst=bool` | full scan payload | writes `latest.json`; warms parquet cache; spins thread pool of 8 + asyncio sem of 4 for catalyst | `sepa.scanner.scan_universe` |
| GET | `/sepa/brief` | — | latest `brief.json` | — | `sepa.brief.load_brief` |
| POST | `/sepa/brief` | — | brief payload | writes `~/.cheetah/scans/brief.json`; pulls catalyst+insider for top5+watchlist | `sepa.brief.generate_brief` |
| GET | `/sepa/candidate/{symbol}` | path | `{symbol, base, catalyst, insider, ipo_age}` | catalyst pulls news+earnings; insider hits SEC EDGAR | `catalyst_for, insider_activity, ipo_age` |
| POST | `/sepa/rescan/{symbol}` | path | analyzed dict for one symbol | force-refreshes parquet cache for symbol | `prices.load_prices(force=True), rs_rank.rs_ranks, scanner._analyze_symbol` |
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
Subcommands invoked by launchd / supercronic
(`python -m sepa.cli {scan|brief|rescan SYM|alerts}`).
`scan --no-catalyst --symbols A,B,C`, `brief`, `rescan SYM` (force price
refresh), `alerts` (runs both position-aware and on-demand price-alert checks).

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

### `providers.py`
Tiny env-var holder. `POLYGON_API_KEY`, `FINNHUB_API_KEY`, `has_polygon()`,
`has_finnhub()`. Polygon routing **not yet wired** — see § 9.

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

The Mac mini deployment uses the `cron` service in `docker-compose.yml`,
running `supercronic /app/crontab`. Crontab lives at `backend/crontab` and
is bind-mounted read-only into `/app/crontab`. Container TZ = `America/New_York`.

| Schedule | Command | Purpose |
|---|---|---|
| `30 16 * * 1-5` | `/usr/local/bin/python -m sepa.cli scan` | EOD scan (16:30 ET) |
| `30 8  * * 1-5` | `/usr/local/bin/python -m sepa.cli brief` | Morning brief (08:30 ET) |
| `*/5 9-15 * * 1-5` | `/usr/local/bin/python -m sepa.cli alerts` | Position + price alerts during market hours |
| `0,5,10,15,20,25,30 16 * * 1-5` | `/usr/local/bin/python -m sepa.cli alerts` | First half-hour of 16:xx (post-close) |

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

Production lives on Ajay's M1 Mac mini. Docker Compose orchestrates four
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
