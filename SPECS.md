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
| GET | `/sepa/candidate/{symbol}` | path | `{symbol, base, catalyst, insider, ipo_age, smart_money, as_of_close, rerate_text}` (2026-10-21: `as_of_close` = the closed session the SEPA read used, null for an in-progress bar; `rerate_text` from `scanner.SEPA_RERATE_ET` — docs/sepa/session_price.md) | catalyst pulls news+earnings; insider hits SEC EDGAR; smart_money fans out to Finnhub + RSS + Reddit (15-min Mongo cache) | `catalyst_for, insider_activity, ipo_age, smart_money_for` |
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
| GET | `/trading/gajjala` | — (admin) | `{date, armed, mode, as_of, status, today[], recent[], journal}` — today's pushed 🚩 A+ alerts LEFT JOIN the lane docs, every row with a served `fate_text` | reads `gajjala_lane`, `gajjala_alerts`, the broker's positions (open rows' last) | `trading.gajjala_entry.tab_payload` |
| POST | `/trading/gajjala/close/{symbol}` | path (admin, armed) | `{ok, state, symbol, errors[]}`; 400 `engine not armed` / `no open 🚩 Gajjala position on XYZ` | cancels the lane's order or flattens its position through `exit_engine.flatten` | `trading.gajjala_entry.close_now` |
| GET | `/trading/status` → `lane_pnl` | — (admin) | {title, since, verdict_text, honesty_text, account, account_text, lanes_total, unexplained, unexplained_text, rows[], untraded_text, positions_text} — every word served | reads trade_journal, gajjala_lane, options_positions, zero_dte_positions, the broker's positions | `trading.journal.lane_pnl_block` |
| POST | `/push/receipt` | `{push_id, endpoint, shown_at}` from the service worker after `showNotification` resolves — PUBLIC path (`_PUBLIC_API_PATHS`): the device's own subscription endpoint is the credential, validated against `push_subscriptions` (2026-10-21, Ajay "Oh man I did not get an A+ alert for it then today" on a sent-3 row) | `{ok, dup}` / 400 / 404 `unknown` (unknown endpoint, unknown push, another user's row — one answer) / 503 | appends ONE receipt per device `{sub: sha1(endpoint), device, shown_at, at}` to the `push_history` row the sender stamped with `push_id` (+ `targets`); never writes `sent`/`failed`/`total`; `/notifications/recent` serves `shown_on` (`text` "shown on 2 of 3 devices (Mac Chrome ×2); no receipt from iPhone Safari") and `/alerts` prints it verbatim — docs/notifications/push_delivery_receipts_2026_10_21.md | `push.receipts.record_receipt`, `push.receipts.shown_on` |

**🚩 Auto-Pilot Gajjala lane (2026-10-20, `backend/trading/gajjala_entry.py`, `docs/trading_gajjala_lane.md`).**
Ajay: "in the autopilot can you stop rest of the strategies and only use the Gajjalas strategies please." Paper-only
lane, tick step (n): today's pushed live 🚩 A+ ENTRY claims (`ledger.alert_of`, line live) are entered the way the 🏁
Track record fills — a day limit `GAJJALA_CHASE_PCT` over the last trade once the tape trades the trigger, the alert's
stop, entry + 1R target, `GAJJALA_RISK_PCT` of equity at risk, 3 a day / 3 open, cancelled unfilled after 180 s or at
the cut-off (regular close − 30 min), flat at regular close − 5 min. Buys only through `entries.enter` (new
keyword-only lane plan: `target_price`, `sizing`, `floors`, `tif`, `order_intent`); the house safety floors apply
while `gajjala_floors` is ON (default). Stock prices go to the broker on Alpaca's grid (4 decimals under $1.00).
POST `/trading/config` takes `gajjala_entry`, `gajjala_floors`, `hot_pullback_entry` (strict booleans, null → true).
UNMEASURED — the study of his setups read no edge.
**v2 (2026-10-21, BUILD_SPEC19 — Ajay "Follow full Gajjala … implement them exactly"): GG's playbook rules.** A MARKET
OTO entry (no take-profit) at the break once the tape trades the trigger (`never_triggered` when the stop prints
first), half of `GAJJALA_RISK_PCT` 0.25% of equity at risk first; on CLOSED 5-minute bars only (`bars.closed_only`):
after `GG_BE_AFTER_BARS` 3 bars a close above the fill moves the stop to the fill and adds the second half (its stop at
the same fill), then the rest trails the 9 EMA; `risk_mult` halves after a losing lane trade (back after a win); the
drawdown window (10% under the peak → 5 trades ≤ 5% together, half off once); a 2-bar cooldown after a stop-out; no
day cap, no stale / thin-R line; `gajjala_floors` default OFF; `entries.enter(ceiling="gg", order_class="oto")` and
`allow_earnings=True` (the p.312 and earnings waivers, strategy-gated to the lane); `exit_engine.tick` (d1) and the
p.308 ratchet skip lane names. Brokers: `submit_bracket(take_profit_price=None)` = OTO, `close_position(symbol, qty)`.
`status.gajjala_lane.rules` serves the rule words + an EMPTY `awaiting` list (2026-10-21, BUILD_SPEC22 Part A — Ajay
"keep what ever Gajjala says for these": the four placeholders are GG's sentences — Kiss & Fly trails the 21 EMA
(`GG_TRAIL_EMA_KF` = `EMA_SLOW`, VR 11.4); after the add fills, the first closed bar closing above every high since the
entry sells `GG_PARTIAL_FRAC` half (VR 11.4, HIS CALL #24 / #25); no entry during a halt until `GG_HALT_CALM_BARS` 1
clean closed bar after the resume — the doc waits (VR 10.1, HIS CALL #26); an A+ risks `GG_DOUBLE_MULT` 2× once the
lane's realized P&L this ET month covers `GG_CUSHION_LOSERS` 2 × the trade's single-rate risk, no loss streak, drawdown
off (VR 11.7); all-in not built). The 🏁 grader is unchanged (+1R). UNMEASURED.

**💵 Auto-Pilot P&L by lane (2026-10-27, `backend/trading/journal.py` lane_pnl, `docs/trading/lane_pnl_2026_10_27.md`).**
Ajay: "Also in autopilot looks like Gajjala's strategy is making money.. Anyway you can can show me which tab made money or not?"
`GET /trading/status` serves `lane_pnl` (`journal.lane_pnl_block` over the SAME `journal.summary()` + the broker's positions): one row per
lane that traded, every word served, printed by the Dashboard's `LanePnlBlock`. `summary.by_strategy` gains `unbooked`, `first_ts`,
`last_ts`, `label`, `url`, `link_text` per lane, plus a `zero_dte` row merged from `zero_dte_lane.journal_block()` and a `hot_pullback`
tag inferred from `entry_reason.lane`. A new ledger kind `exit_fill` (`trading/exit_fills.py`, tick step (e2) + a dry-run-first
back-fill CLI `python -m trading.exit_fills backfill --dry-run | --live`) books the broker's own fill of an engine market sell —
journal-only: NOT read by the p.299 stop rule (`entries._closed_trade_stats`) or progressive sizing (`progressive.last_gains`).
🚩 Gajjala trades pair by alert id (the lane's own `gajjala_exit` / `gajjala_lane` book); the breakeven add's stale journal docs are
marked `superseded`, never deleted. UNMEASURED — a tally of what happened, not a study.

**🏁 Not traded on the 🚩 lane (2026-11-11, `backend/trading/gajjala_untraded.py`, `docs/trading_gajjala_lane.md`).**
Ajay: "Maintain a track record when Alpaca is blocked please, Like we do in Gajjals so I know how our strategies are working".
Every 🚩 lane row with no fill carries `track_state` / `track_text` (`gajjala_entry.ROW_KEYS`): the 🏁 Track record's own
grade of the same alert (`ledger.grade`, one engine), shown as "not traded · 🏁"; the served `untraded` block under Lane
journal totals them beside the lane's fills. Pure reads: no order / broker import, no write; never in the paper P&L,
sizing or the loss streak. UNMEASURED. Contracts "🏁 lane not-traded record (2026-11-11)"; ✨
`autopilot-gajjala-lane-not-traded-record-2026-11-11`.

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

### `forum_chatter.py` — ticker-page chatter lanes (`GET /sepa/chatter/{symbol}`)

#### 2026-10-21 outage words + stale keep + Reddit app key
Trigger: the ticker page printed "all subs returned errors (rate-limit?)" on both Reddit
lanes, StockTwits 0 / 0 / 0, and a raw libcurl timeout line with a curl.se URL.
api.stocktwits.com was down for everyone (timeouts, 0 bytes); Reddit closed anonymous JSON
(www → 403 block page, old.reddit → 404).

- **Served words.** Every lane `reason` is a plain sentence — never a URL, "curl", a libcurl
  code or an exception repr — with a machine-readable `reason_code` beside it.
  - StockTwits (`stocktwits_client.SENTENCE_*`; codes `timeout`, `unreachable`, `http_5xx`,
    `rate_limited`, `challenge`, `http_other`, `ok`): "StockTwits is not answering (timed out
    after 10s)", "StockTwits is not reachable", "StockTwits is down (http 502)", "StockTwits
    rate limit (http 429)", "StockTwits is challenging this client (http 403)", "StockTwits
    answered http 404", "StockTwits answered something that is not JSON". A timeout is a
    `curl_cffi.requests.exceptions.Timeout` (or, on the plain-requests fallback, a class
    whose name carries "Timeout"). The /chatter board carries the same sentence as
    `unavailable_reason` plus `unavailable_code`.
  - Reddit (`reddit_scrape.SENTENCE_*`; per-sub codes `rate_limited`, `blocked` 403, `gone`
    404, `unreachable`, `http_other`, `bad_json`, `auth_failed`; all subs failed → the most
    common code, ties → that order): "Reddit closed anonymous access (http 404) — a Reddit
    app key is needed (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in backend/.env)" (no key),
    "Reddit refused the app key (http 403)" (key set, or a refused token exchange), "Reddit
    rate limit (http 429)", "Reddit is not reachable", "Reddit answered http 502", "Reddit
    answered something that is not JSON". `partial` is unchanged.
- **StockTwits stale keep.** A failed fresh fetch serves the last GOOD StockTwits block of the
  `forum_chatter_cache` row (any age; a cached block with `available` ≠ True is never served)
  with `stale: true`, `stale_since` (epoch of that good read — the row's
  `stocktwits_last_good_at`, else the cached payload's `fetched_at`; clamped ≤ now),
  `stale_reason` (the fresh sentence) and `last_attempt_at`. Reddit / HN / `fetched_at` stay
  the fresh ones; the summary reads the served counts. The cache write keeps the stale block
  and `stocktwits_last_good_at`, so a second outage tick still dates the read correctly. No
  earlier good read → zeros and the sentence + " · no earlier read". A good fetch clears it.
- **Reddit keep** (both lanes down, a cached row exists) serves the cached row with `stale_reason` =
  the served Reddit sentence (the typed "reddit unavailable; showing last good fetch" is gone).
  A cached Reddit lane that was good is kept; a cached lane that had failed (e.g. a row still
  carrying the old "(rate-limit?)" guess) is replaced by the fresh lane and its sentence. The
  summary is recomputed from the served lanes and the served StockTwits block. When StockTwits
  has a good read (fresh or kept), only `payload.stocktwits` + `stocktwits_last_good_at` are
  written; `fetched_at` is left alone, so the Reddit keep still retries on the next visit.
- **Reddit app key (dark until set).** With `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` both
  non-empty (read at call time): POST `https://www.reddit.com/api/v1/access_token` (basic auth,
  `grant_type=client_credentials`, `User-Agent: REDDIT_USER_AGENT`) → bearer cached in-process
  until `expires_in − 60 s`; searches `GET https://oauth.reddit.com/r/{sub}/search` and comments
  `GET https://oauth.reddit.com{permalink}` (no `.json`); one 401 → drop the token, re-auth once
  per call, retry once. A failed re-auth spends it: later requests of the same call (comment
  fetches included) run no further token exchange. Unset → the old.reddit `.json` path, unchanged. The secret is never
  logged, served or stored. Creating the "script" app at reddit.com/prefs/apps and putting the
  two values in `backend/.env` is Ajay's step.
- Tests: `tests/test_stocktwits_client.py`, `tests/test_forum_chatter_outage_2026_10_21.py`,
  `tests/test_reddit_scrape_oauth_2026_10_21.py` (hermetic: monkeypatched seams and
  `httpx.MockTransport` via `reddit_scrape._transport_factory`; a real transport raises).

**Keep only what is worth keeping (2026-10-21, after the first deploy):** the Reddit keep (both lanes down) holds the cached Reddit lanes only when at least one of them was good; a row whose cached lanes had both failed falls through to the normal path — fresh `fetched_at`, `cached: False`, the served sentences written into the row (the 15-minute TTL holds and the old typed guess leaves the cache) — and the StockTwits stale keep still applies there. Before this every ticker read "Cached · hours ago" and re-fetched all four lanes on every open while Reddit stays closed.

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

### Supply/Demand Support-tab frames — supply_demand/timeframes.py (2026-08-29; 1-minute + weekly 2026-10-26)
`TIMEFRAMES`, shortest first: `1min` "Today, to the minute" (1-minute Massive bars, today from 04:00 ET, ≤ 960, `ext_hours`) ·
`5m_today` · `24h` · `15m` · `60m` · `daily` (`DEFAULT_TF`) · `weekly` "The long view" (the Support daily frame resampled by
`chart_maps.ema_frames.resample_ohlcv` — W-FRI, closed=right, label=right; zoom → weeks via `chart_maps.support.weekly_bars_for`:
6m 26 · 1y 52 · 2y 104 · 3y 156 · 5y 260; default 1y; `support_only`). Ajay 2026-10-26: *"Can you build me 1 min bar chart and also
1 week bar chart in the supply and demand"*. Both ride `tf_options(include_live=True)` (Support tab only); `frame_for` refuses both to
every structure caller. The forming minute / week is drawn, never structure; the board block stays daily; neither frame's BUY/SELL is
recorded. UNMEASURED. Contract: `docs/supply_demand/support_levels_tab.md` § "One-minute and weekly bars (2026-10-26)".

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
  `K4_BF_PULL_MIN`–`K4_BF_PULL_MAX` 1–5 (WIDENED 2026-10-18 from 1–3, Ajay *"make the change for Long flags"*); Kiss & Fly `K5_KISS_TOL_PCT` 0.5, `K5_SLOPE_BARS` 3, ≤ `K4_KF_PULL_MAX` 9, every
  pullback close ≥ 9 EMA (`KF_HONOR_ALL_PULLBACK_CLOSES`); Fade base `K4_HF_BASE_MIN`–`K4_HF_BASE_MAX` 6–24, `K6_MERGE_PCT`
  0.5, `K6_TIGHT_PCT` 8.0, `K6_SELL_DECAY` 0.70, trigger `HF_TRIGGER` "base_high"; VCP ≥ `K4_VCP_MIN_CYCLES` 2,
  `K7_CONTRACTION` 0.75, `K7_EMA21_TOL_PCT` 0.5, `VCP_PIVOT_WINDOW` 2 (2026-10-20 `VCP_LIST_FROM_K4` True, Ajay
  *"show me stocks only that have 2 contractions"*: the 🌀 sub cards only reads with ≥ `K4_VCP_MIN_CYCLES` contractions
  — fewer are counted, never carded, never a 🧠 potential; the read's `cycles` field carries the count); Reversal Squeeze `K8_MAX_FLOAT` 10,000,000,
  `K8_DROP_PCT` 8.0, `K8_RECOVER_PCT` 2.0 in `K8_RECOVER_BARS` 3, failed attempt `K8_FAIL_NEAR_PCT` 2.0 /
  `K8_FAIL_DROP_PCT` 8.0 / `K8_FAIL_EVENT_RULE` "distinct", `RS_BASE_MIN_BARS` 1, history chip `K8_HISTORY_SESSIONS` 30 /
  `K8_HISTORY_RANGE_PCT` 50.0, `FLOAT_SUSPECT_POLICY` "ineligible" (spec default); ☀️ K9 `K9_PM_MIN_VOLUME` 1,000,000,
  `K9_AH_CARRY_PCT` 10.0; 🌙 K10 `K10_CLOSE_TOP_FRAC` 0.30, `K10_AH_MIN_VOLUME` 250,000, `K10_AH_MIN_GAIN_PCT` 5.0.
  K11 today's volume on the A+ claim (2026-10-21, GG VR 0.4 "1M is a floor … it must SUSTAIN" — Ajay *"keep what ever
  Gajjala says for these"*): `K11_MIN_SESSION_VOLUME` = `SCAN_MIN_VOLUME` (one number, never a second); a read that broke
  with K1–K10 met (`detectors.K11_STATES` aplus / triggered / stopped) carries the criteria row `k11_volume`; the name's
  session volume from the scanner row under the floor, or no figure (fail-closed, "today's volume unknown"), turns it
  into "broke — not A+" in `detectors.k11_gate` before the push gate — never claimed, never pushed; forming 🧠 reads
  are not judged. The figure reaches `read_all` as ctx `session_volume` (`K11_CTX_KEY`; a caller without the key
  reads K1–K10 only). HIS CALL #27: A+ counts before / after 2026-10-21 are not comparable. UNMEASURED.
  Entry = the entry bar's high trades above the trigger on a CLOSED bar; stop = the trigger bar's low (the bar before the entry bar) / the base's low.
- **Reads**: **A+** = every rule met and the entry bar closed — the only pushable state. Listed, never A+, never pushed:
  **"long flag"** (Bull Flag pullback past `K4_BF_PULL_MAX`, up to `K4_BF_LONG_FLAG_MAX` 5; more = invalid — band EMPTY
  since 2026-10-18 while `K4_BF_LONG_FLAG_MAX` is None: 1–5 bars = A+, > 5 invalid; the variant path stays config-driven),
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
  900. ℹ️ panel: `rules_info` section "gajjala", built from `constants.py`. Every payload serves `counts_legend`
  (2026-10-18, DECISIONS15 D1: `tab.count_legend()` → `[{key, word, text}]` over `LEGEND_KEYS` = the seven
  `COUNT_STATES` + `awaiting_answer`, `listed`, `potential`, `track` — words only, `counts` unchanged) and `subs[].title`
  (the legend's potential text on the 🧠 sub, None elsewhere); the FE prints them as hover titles and one folded ⓘ.
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
  every setup sub, and the sub `POTENTIAL_SUB` (last in `SUBS`) = roll-up + 📈 Track + 👀 watch line (drawn in that order since 2026-10-18 — the live tiles first, Ajay: "bring them to the top of the view"). Tracker: Mongo
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
  (`latest_cron`) is within `STALE_AFTER_SEC` — opens alone never hide a dead cron (A10). Closed bars only. UNMEASURED. 2026-10-23: the board keeps the 🔄 button on the strip in a closed
  session too (a tap prints the served closed line) and dims it only while the pass it asked for runs, the served reason
  as its title — `docs/gajjala/gajjala_tab_2026_10_13.md` §🔄 The button stays on screen.
  Doc: `docs/chart_maps/gajjala_on_open_scan_2026_10_15.md`; contracts "🔄 Gajjala scan on open + 🎯 A+ banner
  (2026-10-15)".
- **🚫 Not eligible at Fidelity** (2026-10-17, Ajay: *"Or just add a tag that not eligible on Fidelity"*) — his own list
  (`BROKER_FLAG_SEED` empty + `gajjala_state` `_id "broker_flags"`, `store.broker_flags` = (seed ∪ added) − removed; a
  store read fault falls back to the seed and the strip says "your list could not be read this time — the tags are off
  until the next read"), served `broker_text` on every Gajjala row that names a symbol + the owner's `broker_flags` strip
  and 🚫 card toggle — owner = the primary admin only (`ollama_chat.api.is_primary_admin`; anyone else null); the A+ / 🧠
  bodies say " · 🚫 not eligible at Fidelity" before UNMEASURED and the titles end " · 🚫"; `alerts.COUNT_KEYS`
  "broker_flagged"; GET / POST / DELETE `/chart-maps/gajjala/broker-flags` (owner, stealth 404; bad ticker 400, read fault
  503); nothing hidden, nothing muted, nothing guessed (a pre-screen from Fidelity's published rules = HIS CALL Q2); since
  2026-11-09 his names sit at the BOTTOM of every card board by his word (the 📊 bullet below). Doc
  `docs/gajjala/broker_flags_2026_10_17.md`; contracts "🚫 Gajjala broker tag (2026-10-17)"; ✨
  `chart-maps-gajjala-broker-tag-2026-10-17`.
- **🎾 lowest float on top** (2026-10-18, Ajay: *"for the float lower the better is what I wanna follow so sort it by
  lowest on top"*; GG S8 21:04 "the lower the float the better", no cutoff). On the `reversal_squeeze` sub only:
  `RS_FLOAT_SORT` "within_state" (MINE — state rank first, A+ › triggered › ready › forming › partial › stopped, then
  float ascending, unknown float last — none / 0 / suspect under `FLOAT_SUSPECT_POLICY` "ineligible" — then the existing
  tiebreaks; "global" = float above the state, HIS CALL Q1). The word is served: `tab.RS_ORDER_TEXT` "🎾 lowest float on
  top" as `order_note` on the squeeze sub, null on the other setup subs and absent on the list / 🧠 / 🏁 / 📓 subs; the FE prints it verbatim and types none. Same day,
  his word: `K8_MAX_FLOAT` 10,000,000 and `NO_TRADE_AFTER_OPEN_MIN` 15 UNCHANGED (*"Keep the float reduce and also 15
  mins filter."*). UNMEASURED. Doc + HIS CALL Q1–Q6: `docs/gajjala/k4_long_flags_float_2026_10_18.md`; contracts
  "🚩 K4 long flags + 🎾 float order (2026-10-18)"; ✨ `chart-maps-gajjala-float-sort-2026-10-18`,
  `chart-maps-gajjala-long-flags-2026-10-18`.
- **📊 Highest volume on top + 🚫 his names at the bottom** (2026-11-09, Ajay: *"Ok sort any stocks by volume on all
  Gajjala's charts"* / *"The ones I am reporting they are not on Fidelity put them at the bottom"*). `tab.order_key`'s
  sort slot inside every state on every setup sub = (today's scanner volume DESCENDING — the card's own Volume number,
  `GC.VOLUME_SORT_SETUPS` = the float tuple, unknown last —, then the 2026-10-18 float ascending), placed by
  `RS_FLOAT_SORT`; ➖ keeps its 2026-11-07 EMA-gap rank first; `potential.order_key` takes the same swap (armed, volume ↓,
  float ↑). Then `tab.broker_bottom` partitions every card board (the five setup subs, 🧠, ☀️, 🌙): the names on his 🚫
  list move to the END in the same order, after the limit cut (the list only reorders, never drops a card; the 🧠 strip
  rows too; the ℹ️ 🚫 line says so), for EVERY viewer (the words stay owner-only — the
  nothing-hidden invariant holds); never hidden, counts and the 🏁 untouched. Served words: `order_note` on every setup
  sub (`VOL_ORDER_TEXT` / `RS_ORDER_TEXT` / `HF_ORDER_TEXT`) and the 🧠 sub (`POT_ORDER_TEXT`); `broker_flags.order_text`
  on the owner strip. Display order only. The morning's float-on-every-sub step: `docs/gajjala/float_sort_all_setups_2026_11_09.md`.
  Doc `docs/gajjala/volume_sort_broker_bottom_2026_11_09.md`; contracts "📊 volume on top + 🚫 at the bottom (2026-11-09)";
  ✨ `chart-maps-gajjala-volume-sort-broker-bottom-2026-11-09`; tests `tests/test_gajjala_volume_sort_2026_11_09.py`.
  Amended 2026-11-11: on the 💋 sub the slot takes `tab._kf_slot` (relative volume ↓, then the 9 EMA distance ↑) AHEAD
  of (volume ↓, float ↑) and `order_note` is `KF_ORDER_TEXT` — see the 💋 row below.
- **🏠 "/" opens Gajjala's tab for the primary owner** (2026-11-10, Ajay: *"Then default my landing page to Gajjala's tab
  in chartmaps on the app always."*) — `frontend/src/lib/landing.ts` `ownerLanding(target, isPrimaryOwner)` +
  `OWNER_LANDING_TAB: CmTab = 'gajjala'` (type-only import: `chartMaps.ts` stays out of the entry chunk); `App.tsx`
  `SmartLanding` waits for features, menu AND `useCurrentUser()` (a loader, never a wrong redirect; a failed `/auth/me` →
  today's target), then `ownerLanding(pickLanding(f.features, !!menu.is_admin), !!user?.is_primary_admin)` →
  `/chart-maps?tab=gajjala` only when Chart Maps is the winning landing feature AND the viewer is the primary owner
  (`is_primary_admin` from `/auth/me`; never an email in the bundle; a co-owner with `is_admin` keeps the bare path).
  Every other viewer and every other target come back byte for byte; the catch-all route and the no-access redirect pass
  through "/" too, so they follow. `DEFAULT_TAB`, the `CM_TABS` order, the menu's Chart Maps link and a hand-typed
  `/chart-maps` are untouched (HIS CALL: co-owners / everyone, the menu link, the bare path — an iOS home-screen app that
  resumes its last page never passes through "/"). Doc `docs/gajjala/landing_gajjala_tab_2026_11_10.md`; contracts
  "🏠 "/" opens Gajjala's tab for the primary owner only (2026-11-10)"; ✨ `chart-maps-landing-gajjala-tab-2026-11-10`;
  tests `src/lib/landing.test.ts`, `src/App.landing.test.tsx`.
- **🗣 Rule rows in plain words (K1–K11)** (2026-11-10, Ajay: *"Also please use common vocabuluary like volume dried:
  "K3 base volume ≤ 0.5× the squeeze-back run — max 98933 (≤ 36008)""* + *"not jus k3 please up date what he means in
  simple terms acroos k1 to k10"*; "he" = GG) — **wording only**: no gate, rule, threshold, key, number, push, count or
  data change. Every `ok`, `missed`, state, grade, trigger and stop is byte-identical to the tree before the build (the
  stripped snapshot `backend/tests/fixtures/gajjala/plain_words_stripped_2026_11_10.json`, written on the untouched
  tree, is reproduced byte for byte by `tests/test_gajjala_plain_words_2026_11_10.py`). ONE engine:
  `chart_maps/gajjala/detectors.py` `criterion(key, label, ok, value, need)` composes a row once and the FE prints it
  (`criteriaText` = "<mark> label — value (need)"; the FE types no rule word), so 🚩 Gajjala's, the 1-minute page and
  🧪 Audited change together; 🥇 Luk's tab is out of scope. Row shape: label = the K id + a plain phrase with no number,
  comma or em-dash (the "missed:" pill joins the labels); the number moves into `need`, in words, built from the
  enforcing constant by name (`part_words(GC.K3_VOL_FRAC)` → "half"); `value` says what was seen, with thousands
  separators. His row now:
  `✗ K3 volume dried up in the base — busiest bar 98,933 (every bar must be ≤ 36,008: half the average bar of the run back up)`.
  Vocabulary, one word per idea: demand bar → big green bar · demand leg → run up · leg mean → the average bar of the
  run up · squeeze-back run → the run back up · max → busiest bar · ≤ 0.5× → half · 🌀 cycle → contraction; GG's own
  words kept (kiss, honors, merged, tennis ball action, quiet base). The same words in the reason lines, the 🧠 legend
  sentence (`potential.py`: "a run up alone is not a potential"), the 🧠 strip sentence (`tab.py`),
  the 📓 knob rows (`playbook.knobs()`: K1, K2, K3, K5,
  K6, K7, K8, H1, H2, H3), the ℹ️ Rules panel (`rules_info._gajjala_section`: picks 2–7, stop 1, one alert line, the
  note), the 🧪 K3S rule text (`audited_rules.py`; the registry param keeps "0.5×"), `scripts/gajjala_examples.py`
  `INVALID_RULE` (the new reason fragments ADDED beside the old ones, so old stored reads still classify) and the
  /notifications 🧠 sentence. Byte-identical on purpose: the `k6_merge` VALUE (`tab._EMA_GAP_RE` fullmatches it), every
  "awaiting …" reason (`alerts.py` / `tab.py` read `reason.startswith("awaiting")`), the K11 row, the red-closes row,
  the state words, the variant names, the K4 🌀 label, `NOT_APLUS_REASON`, GG's quoted lines and `alerts.ENTRY_WORDS`.
  Rides along: the kiss sign fix ("-1.4% above" → "low 1.4% under the 9 EMA"). **Stored rows keep the words of the pass
  that wrote them** — nothing relabels at serve time, so stored reads (cards and 🧠 strip rows) written before the
  first pass after the deploy keep the old words until they age out; 🏁 and 🕰️ rows carry none of the row words.
  Goldens regenerated text-only (allow-list `body`,
  `first_reason`, `grade_label`, `label`, `need`, `reason`, `state_label`, `text`, `value`, `why` + `title` only at
  `subs/<n>/title`; `_recipe` byte-equal): the four FE fixtures, the GG5 BOARD golden and, for the first time, the GG5
  WRITES golden (302 string leaves; HIS CALL #1 in the doc: it was not asked first).
  **430 px, measured** in the real page's own nodes (local preview at `innerWidth` 430; pill and row content width
  382.8 px; the Range line count and `round(height / line-height)` agree on all 28 measured items): **PASS** — no
  "missed:" pill takes more lines than its old string (6 of 15 one line shorter, 9 equal, none longer); nothing clips or
  scrolls sideways. Rows grow on purpose: `k2`, `k8_tennis` and `k8_failed` 2 → 3 lines, the grade-B tile line 1 → 2;
  his K3 row stays at 2.

  | String | node | chars old → new | lines old → new |
  |---|---|---|---|
  | worst pill + K11 · 🚩 Bull Flag | pill | 218 → 211 | 4 → 4 |
  | worst pill + K11 · 💋 Kiss & Fly | pill | 353 → 296 | 7 → 6 |
  | worst pill + K11 · ➖ Horizontal Fade | pill | 303 → 240 | 6 → 5 |
  | worst pill + K11 · 🌀 Intraday VCP | pill | 274 → 267 | 5 → 5 |
  | worst pill + K11 · 🎾 Reversal Squeeze | pill | 240 → 204 | 5 → 4 |
  | worst pill, no K11 · 🚩 | pill | 132 → 125 | 3 → 3 |
  | worst pill, no K11 · 💋 | pill | 267 → 210 | 5 → 4 |
  | worst pill, no K11 · ➖ | pill | 217 → 154 | 4 → 3 |
  | worst pill, no K11 · 🌀 | pill | 188 → 181 | 4 → 4 |
  | worst pill, no K11 · 🎾 | pill | 154 → 118 | 3 → 2 |
  | single miss · 🎾 K3 only | pill | 80 → 68 | 2 → 2 |
  | single miss · ➖ K6 selling only | pill | 98 → 58 | 2 → 2 |
  | single miss · 🌀 K7 tighter only | pill | 80 → 79 | 2 → 2 |
  | single miss · 🎾 failed try only | pill | 80 → 74 | 2 → 2 |
  | K11 label alone (untouched) | pill | 122 → 122 | 3 → 3 |
  | grade-B pill · 🌀 | grade pill | 89 → 88 | 2 → 2 |
  | grade-B tile line · 🌀 (row label instead of the raw key) | tile why | 31 → 64 | 1 → 2 |
  | row · his K3 row (🎾) | row | 66 → 123 | 2 → 2 |
  | row · `k2` (🚩) | row | 86 → 143 | 2 → 3 |
  | row · `k8_tennis` (🎾) — also the longest OLD row | row | 113 → 168 | 2 → 3 |
  | row · `k8_failed`, "1 failed try today" | row | 109 → 173 | 2 → 3 |
  | row · `k8_failed`, "no failed try today" | row | 109 → 174 | 2 → 3 |
  | row · `k8_failed`, "none that counts" — the longest NEW row | row | 109 → 191 | 2 → 3 |
  | tile line · longest NEW reason (🎾 "no tennis ball action today …") | tile why | 56 → 108 | 2 → 2 |
  | tile line · longest OLD reason (💋 "no risk — …", unchanged) | tile why | 77 → 77 | 2 → 2 |

  With the new words injected at 430 px: ℹ️ Rules → Gajjala panel (8 picks / 6 stops / 3 alerts; 6 picks, 1 stop, 1
  alert and the note reworded) is 386 px wide with 0 overflowing nodes and no sideways scroll; 📓 Playbook → knobs
  serves 19 of 19 (10 reworded) with 0 overflowing nodes. Doc `docs/gajjala/plain_words_2026_11_10.md` (12 open
  HIS CALLs); contracts "🗣 Gajjala rule rows in plain words (2026-11-10)"; ✨
  `chart-maps-gajjala-plain-words-2026-11-10`; tests `tests/test_gajjala_plain_words_2026_11_10.py` (re-pinned:
  `test_gajjala_detectors.py`, `test_gajjala_vcp_listing.py`, `test_rules_info_gajjala.py`,
  `test_gajjala_audited_k3s_rules_2026_11_09.py`; FE `src/pages/Notifications.gajjala_potential.test.tsx`; ✨ order +1
  in `GajjalaBoard.promo_chip.test.tsx`, `newFeatures.gga_mods.test.ts`, `newFeatures.luk.test.ts` and `contracts.mjs`;
  docstring / comment only: `test_gajjala_audited_pass.py`, `test_gajjala_variant_gg5_identity.py`).
- **⚡ Enter like GG** (2026-11-11, Ajay: *"Here is how he enters please tell me to enter based on this"*) — the card's
  ONE plan line is served: `tab.plan_text` → "Entry above X · stop Y · risk r%" (on `tab._px`, the broker grid; "Entry
  above" only when `ledger.plan_of` is the first plan, else "trigger …"); `GajjalaBoard` prints `read.plan_text`
  verbatim. `chart_maps/gajjala/break_watch.py` watches the ARMED 🧠 plans on the live socket (its own "gg-brk" worker)
  and records the ⚡ intrabar break; `GAJJALA_BREAK_PUSH_MODE = "shadow"` (recorded on /alerts, no device — HIS CALL #1),
  `GAJJALA_BREAK_PUSH_KIND = POTENTIAL_PUSH_KIND` (HIS CALL #2). The bar-close A+ is unchanged. UNMEASURED. Doc
  `docs/gajjala/entry_break_2026_11_11.md`; contracts "⚡ Gajjala enter like GG (2026-11-11)" + the re-pinned "🚫 Gajjala
  no-risk A+ · one price grid"; ✨ `chart-maps-gajjala-entry-break-2026-11-11`.
- **🧠 Proposals applied** (2026-11-11, Ajay: *"Also apply your proposal too."*) — `POTENTIAL_PUSH_ARMED_ONLY` (a 🧠 rings
  only once armed; held "building") and `POTENTIAL_ONE_RING_PER_NAME` (held "name_rang"), read by name in
  `potential.py`; the 1-minute A+ push adds `alerts.CHASE_TEXT` facts (GG5 byte-identical); `tab.VOL_DRIED_TEXT` 💧 chip;
  🌅 `tab.day2_block` on ☀️ (a list, no push); 🔝 `tab.focus_block` marks the first `FOCUS_N` cards (display only, never
  reorders). Studies #5–#7 pre-registered, not run. UNMEASURED. Doc `docs/gajjala/proposals_applied_2026_11_11.md`;
  contracts "🧠 armed-only · one ring per name (2026-11-11)", "💧 🌅 🔝 card extras (2026-11-11)"; ✨
  `chart-maps-gajjala-proposals-applied-2026-11-11`.
- **🧭 Setup stages on every card** (2026-11-11, Ajay: *"… what stages a stock has crossed in the past like Bullflag ->
  EMA Kiss and Fly -> and Horizontal -Fade … with time stamps if its same day"*) — `chart_maps/gajjala/stages.py` (pure:
  imports constants only) turns the 🧠 tracker's `state_path` + the live A+ that rang (`tab._entry_times`) into tags,
  read ONCE per board by `tab._stage_tag`; `GgStages.tsx` prints the served words on 🚩, 1-minute and 🧪 cards. A clock
  for today's session only, the date otherwise. Display only. Doc `docs/gajjala/setup_stages_2026_11_11.md`; contracts
  "🪜 Gajjala stages tags (2026-11-11)"; ✨ `chart-maps-gajjala-stages-2026-11-11`.
- **💋 EMA Kiss: relative volume first, closest to the 9 EMA next + the "lifting off the 9 EMA" toggle** (2026-11-11,
  Ajay: *"Sort by relative volume, and closer to the EMA."* / *"This filter is needed for EMA Kiss atleast"*). Data:
  `context.warm_squeeze_history` stores `avg_vol_50` = `MB.avg_volume_before` (the 🎾 chip's own daily frame, no new
  read; only when 50 closed sessions exist); `run.run_pass` sets `ctx["rvol"]` = `drop10_tab.rvol_read` over THIS pass's
  session volume (`sv[s]`, never the stored scan row) — projected in RTH, none pre-market. Order: on the 💋 sub only
  (`GC.RVOL_SORT_SETUPS`), `tab._kf_slot` puts (relative volume ↓, the K5 row's 9 EMA distance ↑; each unknown last in
  its state, never 0; `GC.KF_EMA_SORT` "rvol_first") ahead of the 📊 (volume, float) slot inside each state (A+ /
  triggered, then forming-ready = kissing now, on top — the existing ranks). Card stat "Rel volume" (`rvol_text`), a
  `list_note` on a mixed board, `order_note` = `KF_ORDER_TEXT`. Toggle (addendum): each 💋 card serves `kiss_now`
  (true = A+ / triggered / forming-ready; false = not kissing; null = unknown, never hidden), the sub serves
  `kiss_filter` {label, hint, hidden_text_template}; `GajjalaBoard` chip default OFF (localStorage `gg-kiss-filter`), ON
  hides only `kiss_now === false`, never reorders. Display only: no gate, rule, push, count or 🏁 change. UNMEASURED
  (the 11-11 loudest-three read was null-to-negative). Doc `docs/gajjala/kiss_rvol_sort_2026_11_11.md` (13 HIS CALLs);
  contracts "💋 EMA Kiss rel volume order + lifting-off toggle (2026-11-11)"; ✨ `chart-maps-gajjala-kiss-rvol-sort-2026-11-11`;
  tests `tests/test_gajjala_rvol_avg_2026_11_11.py`, `tests/test_gajjala_kiss_rvol_sort_2026_11_11.py`,
  `GajjalaBoard.kiss_rvol.test.tsx`.
- **📌 Trader names join the list** (2026-10-27, Ajay: *"Can you track this guy please? and his tickers"* +
  https://stocktwits.com/algo888, then *"Add them to Gajjals, they are pretty good"*). `chart_maps/gajjala/trader_names.py`
  reads the STORED posts of every `traders/registry.py` row with `"gajjala": True` (today: algo888 only) and, inside
  `run.run_pass` AFTER `scanner.scan_rows` (PURE, GG's, byte-identical — never says "trader") and BEFORE
  `scanner.record_scan` (`TN.run_step`, FENCED: a raise leaves the scan as his scanner built it; `TN.recount` after the
  split hold-out), ADDS his names posted in the last `TRADER_NAMES_FRESH_SESSIONS` market sessions (today included),
  newest first, at most `TRADER_NAMES_MAX` a pass, that resolve in today's snapshot (`sepa.symbols.for_yahoo`) — inside
  GG's `SCAN_MIN_PRICE`–`SCAN_MAX_PRICE` band and the instrument rule, never OTC, WITHOUT GG's change and volume floors
  (HIS CALL #1). A name his scanner already lists is TAGGED, never duplicated. Rows carry `source "trader"`; the pass's
  `qualifiers` stay GG-only. Served tag 📌 `trader_text` on every card, row and push (A+ / 🧠 body only, titles
  unchanged), the strip's `trader_text` / `trader_skip_text` (skip reasons `SKIP_TEXT`), the legend row "trader" LAST,
  the ℹ️ scanner clause (`_gg_trader_clause`, picks stay 8), the 🏁 row's `trader_text` from the claim doc. AMENDMENT A2:
  a 📌 add's 🧠 push is HELD (`TRADER_HOLD_TEXT`) while the session volume the pass read is under `SCAN_MIN_VOLUME`; the
  A+ is K11. The cron pass re-reads a flagged StockTwits account every `TRADER_REFRESH_SEC` (`trader_refresh` memo;
  `main` passes `trader_fetch=TN.default_fetch`; tests, dry, replays and the on-open pass never fetch). Every TRADER_*
  constant is tagged MINE; no SCAN_* / K* value changed. **UNMEASURED** — the closest class this app measured
  (promo-account first tags) read INVERTED. Doc `docs/gajjala/trader_names_2026_10_27.md` (HIS CALLs #1–#10); contracts
  "📌 algo888 tracked + his names into Gajjala's scan (2026-10-27)"; ✨ `chart-maps-gajjala-trader-algo888-2026-10-27`.
- **🎪 Promo-circuit names join the list** (2026-10-29, Ajay: *"should we pull stocks from PROMO circuit by default every
  day they are having some good catched but I do wanna run them against Gajjalas strategies"*).
  `chart_maps/gajjala/promo_names.py` (SOURCE "promo", tag `PROMO_TAG` 🎪) reads the STORED `promo_circuit_tags` (one
  Mongo read, never a sweep or a fetch; `Deps.promo_tags`, wired by `main` on the cron and on-open paths), keeps roster
  accounts, prunes shotgun one-offs with `promo_circuit.prune_shotgun_tags` over the page's 14-day window, and takes the
  tickers tagged on the session's ET date (first or later tag — the page's "today" rule). Right after the 📌 step and
  before `scanner.record_scan` (`PN.run_step`, FENCED: a raise adds nothing and counts `promo_failed`), each name runs
  the 📌 add check (`trader_names.candidate_row`: snapshot, dated print, prior close, instrument rule, GG's price band —
  no change or volume floor for the ADD); the survivors are ordered by today's % change and the first
  `PROMO_NAMES_MAX` 25 join (Cheetah default, in `CHEETAH_DEFAULTS`, HIS CALL #1), the rest COUNTED `promo_over_cap`;
  the cap bounds the SESSION's listed 🎪 adds (`promo_names.listed_today`: an earlier pass's add keeps its slot, critic
  F3), and `run.py` loads GG's own names before the 📌 / 🎪 adds.
  A listed name (GG's or a 📌 add) is TAGGED (`promo` / `promo_text`; a 📌 row keeps `trader` too). GG's 1M floor stays
  on every push: a 🎪 add's 🧠 push is HELD (`PT.PROMO_HELD`, `PROMO_HOLD_TEXT`, count `promo_held` only when a promo
  map was handed) on GG5 and the 1-minute page; the A+ is K11. Counts `promo_added` / `promo_tagged` /
  `promo_skipped` / `promo_over_cap` / `promo_failed` and the `promo` block appear ONLY when the source ran — an
  unwired or empty source adds no key (the GG5 identity fixture is unchanged). Served: `promo_text` on tiles / rows /
  claims / tracker docs / 🏁 rows and in the push bodies (titles unchanged), strip `promo_text` / `promo_skip_text`,
  the legend row "promo" last (`tab.LEGEND_KEYS_PROMO`, only when the source ran), the ℹ️ note clause
  (`_gg_promo_clause`), `/alerts/status` `promo_added` / `promo_held` / `promo_held_text`. **INVERTED** (Promo first
  tags, `docs/catalysts/promo_tag_study_2026_09_21.md`) and **UNMEASURED** on GG's setups — a watchlist feed for his
  rules, not an edge. Doc `docs/gajjala/promo_names_2026_10_29.md` (HIS CALLs #1–#6); contracts "🎪 Promo names on
  Gajjala's scan (2026-10-29)"; ✨ `chart-maps-gajjala-promo-names-2026-10-29`.
- **🚩 Gajjala's chart on the stock page (2026-11-06)** — Ajay, verbatim: "If I click on Gajjalas tab stocks show me
  "Gajjalas chart" in supply and demand of his view by default mainly.." and "Like if he looks at 24 hours or 2 week or
  anything else that is what I would like to see". The served 🚩 tile href (setup cards, 🧠 potentials, ☀️/🌙 movers;
  GG5, the 1-minute page and 🧪 Audited) = `tab.chart_href(sym, tf, v)` = `board._href(sym)` + `&tf=<key>` — the ONE
  `board_mod._href(sym)` call in `gajjala/tab.py`; `board._href` is unchanged for every other board and 🥇 Luk's cards
  stay on the daily chart. The key is the Support-tab frame of the frame the card is DRAWN on (`fr["tf"]`; a bar-less
  tile → the variant's primary), read BY NAME from `constants.CHART_FRAME_KEY_CONST` (`"5m"` → `timeframes.M5_TODAY`
  "Today, for an entry", `"15m"` → `M15` "The last two weeks", `"1m"` → `M1_TODAY` "Today, to the minute") against
  `supply_demand/timeframes.py` at call time — never the bare `5m` (the 24-hour alias) nor `1m` (the one-month window);
  `CHART_TF_PARAM = "tf"`. The stock page (`pages/SepaCandidate.tsx`) reads `?tf=` / `?window=` ONCE on first paint into
  its plain state (`parseTf` / `parseWindow` / `retiredTf`, a retired key says so through `retired=`); a later pick wins,
  and a /sepa → /sepa navigation does not re-read. The landed zoom is the link's own `?window=` or the house 1 year
  (`SEPA_SUPPLY_WINDOW`), never the picker's frame pin (`windowForFrame` → 6 months): SupportLevels remembers the MOUNT
  window as what "The big picture" comes back to, so daily returns at 1 year. The chart under his frame draws the HOUSE
  averages (`board.MA_SPECS` 9 EMA / 20 SMA / 200 SMA), not his 21 EMA (verified_rules T2) — HIS CALL #7. The GG5 BOARD
  golden and the three FE board goldens moved href-only (the WRITES golden byte-identical). Docs
  `docs/gajjala/gajjala_tab_2026_10_13.md` § "🚩 The card's href carries his frame (2026-11-06)" and
  `docs/gajjala/frontend_2026_10_13.md` § "🚩 Gajjala's chart on the stock page (2026-11-06)" (HIS CALLs #1–#7);
  contracts "🚩 Gajjala's chart on the stock page (2026-11-06)"; ✨ `chart-maps-gajjala-chart-frame-2026-11-06`.
  No gate, rule, threshold, claim or push changed. UNMEASURED. Not advice.
- **🎾 Short-interest label · ➖ 9/21 EMA rank (2026-11-08)** — Ajay, verbatim: "Also for the reversal squeeze I need
  short interest to be show on all the 3 of his tab as a label." and "On the horizonal fade I need a ranking in
  horizontal fade when the stock 9 EMA and 21 EMA are converging or close to converge on all tabs". 🎾: FE only —
  `components/GgShortInterestLabel.tsx` prints the SERVED 🩳 chip text (`short_interest/read.py chip_text`; hover =
  `title_text`) in bold under the plan of every `reversal_squeeze` card on GG5, the 1-minute page and 🧪 Audited through
  the ONE hook `useShortInterest` + `siChip` (one bulk GET per board, unchanged); the muted `ShortInterestChip` is skipped
  on 🎾 cards only (Rule #5: the SI prints once); no record → nothing, never a zero; a label, never a gate — GG has no
  short-interest rule in any source (verified_rules U10). ➖: `constants.HF_EMA_SORT = "pre_break"` (MINE; the three
  orders in `HF_EMA_SORTS`) — on the ➖ sub the reads that have NOT broken out (forming AND partial) rank together by
  `tab._ema_gap_pct(read)` = the k6_merge criterion's printed value (|9 − 21 EMA| as % of close at the read's ref bar, a
  SNAPSHOT: "closest to merged", never a direction — HIS CALL #16) ascending, unknown last, stashed as
  `gajjala._ema_gap_pct` and popped by `_strip_private`; A+/held/triggered/stopped keep today's key on top; the sub
  serves `tab.HF_ORDER_TEXT` as `order_note`. The GG5 BOARD golden moved by the ➖ order plus that one string;
  `gg5_writes` byte-identical; no band on any GG5 card. Docs `docs/gajjala/card_labels_2026_11_08.md` and
  `docs/gajjala/fade_ema_rank_2026_11_08.md` (HIS CALLs #6–#10, #16); contract "🧪 entry zones · 🎾 SI label · ➖ EMA
  rank (2026-11-08)"; ✨ `chart-maps-gajjala-squeeze-si-label-2026-11-08`, `chart-maps-gajjala-fade-ema-rank-2026-11-08`.
  No gate, rule, threshold, claim or push changed. UNMEASURED. Not advice.
- **🎾 GG's marks on the Reversal Squeeze chart · wide card · prior-session tail (2026-11-08)** — Ajay, verbatim, with
  GG's own annotated TPST chart: "I need something like this but that big of circle for reversal squeen mainly on the cart
  itself also increase the width of the reversal sqeeze chart to show more bars" / "This is from Gajjals" / "They don't
  have to be circles but indicators did you build them already?". `detectors.reversal_squeeze` stores
  `setups.reversal_squeeze.structure = {tennis, run, base, attempts}` boxes `{from_t, to_t, lo, hi, bars}` from the indices
  it already had (`_paired` = `bool(_pairs)`, identity pinned under both K8_FAIL_EVENT_RULE values; present on every read
  with a tennis ball incl. invalid, absent on none / float-gated; no rule reads it). The GG5 pass stores
  `tile.bars5_prior / curves5_prior / vol_avg5_prior` for every name (`bars.tile_prior_payload`, `RS_TILE_PRIOR_FROM_ET`
  15:00 ET → `RS_TILE_PRIOR_TO_ET` 20:00 = ET_AFTERHOURS_CLOSE, caps 60 + 192 = 252 derived — MINE; 0.57–2.68 ms per call);
  `run_1m.py` untouched. `chart_maps/gajjala/squeeze_marks.ellipses` serves `ellipses` `{kind, from_t, to_t, lo, hi, label,
  note, tone}` on 🎾 cards only (ah · attempt · tennis · run · base · entry; a mark only when both stamps are served bars and
  the drawn frame is the read's; the AH mark = the prior after-hours bars clearing the K9 carry line via `scanner._at_least`
  + `K9_AH_CARRY_PCT`; the entry mark rides the A+ marker rule); the hover note QUOTES GG; no red "close or add" (E3/E5,
  his 11-06 "keep it") and no "held its AH level" (a threshold). FE: `CmEllipse`, `lib/ggEllipses.ts` (PAD_X 0.6 bars,
  PAD_Y 3, MIN_R 5, label 8 — drawing constants, MINE; magenta #e879f9 structure, house green entry), one clipped
  `g.pc-gg-ellipses` layer after the candles with NO pointer-events none (the refix: the `<title>` must be reachable);
  `markerIndex` matches the full stamp first (the A+ tag draws on intraday cards for the first time — 🚩, 1-min, 🧪 and
  🥇 Luk's, HIS CALL #13); `.gg-card.gg-wide { grid-column: 1 / -1 }` on 🎾 cards (never `span 2`; one column ≤ 640 px).
  Goldens regenerated by recipe, delta proved additive: gg5_writes (+18 prior-tail keys on 6 docs; its 🎾 reads found no
  tennis ball, so no `structure` there), gg5_board byte-identical (no 🎾 tile in the fixture), the FE potential golden
  (+`ellipses: []`); 1m and on_open unchanged. Doc `docs/gajjala/squeeze_chart_2026_11_08.md`
  (HIS CALLs #1–#15); contract "🎾 GG's marks on the Reversal Squeeze chart (2026-11-08)"; ✨
  `chart-maps-gajjala-squeeze-chart-2026-11-08`. No gate, rule, threshold, claim or push changed. UNMEASURED. Not advice.

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
- **🎯 A+ filter + win/loss charts** (2026-10-26, Ajay: *"Once done can you give me a  A+ filter in the track record I
  wanna see how many of the A+ were successful draw some charts to show the winning vs losing percentages of A+ trades
  please"* and *"I need these charts on Track Record page"*). `served_block` adds `kinds` (`KIND_KEYS` all · aplus,
  `KIND_LABELS` + the ROW count, ⏪ counted apart on "all"), `kind_param` `kind` (FE-only, `?kind=aplus`, never on the
  GET), `kind_empty_text`, `categories_aplus` (`_categories` over the A+ rows) and an always-served `aplus` block
  (`aplus_block`): its OWN A+ rows `aplus.days` (live + shadow, `APLUS_LINES`; ⏪ replayed out; cut by the same
  `LEDGER_ROWS_MAX` with its own `more_text`, the counts cover every A+ row), the **pooled** live + shadow counts tallied
  by the headline's own thin rule (`_tally_into`, % = `_win_pct`, `loss_pct` = 100 − pct), `counts_text` (lead
  `APLUS_LEADS`), `split_text`, `replayed_note`, `honesty` (`APLUS_HONESTY`) and three charts (`APLUS_CHART_KEYS`
  outcomes · by_setup in `GC.SETUPS` order, never by % · by_day ascending) whose every label, number and % is served.
  The 🧠 headline is byte-identical. FE: `GajjalaAplusCharts` (hand SVG, geometry only) on the list view ALWAYS
  (AMENDMENT A1 — his second line answered H2); the 🎯 chip narrows the row list only; the 🕰️ timeline draws none of it.
  **UNMEASURED** — the 2026-10-14 study read NULL. Contracts: "🎯 A+ filter + win/loss charts on the 🏁 Track record
  (2026-10-26)"; ✨ `chart-maps-gajjala-aplus-filter-2026-10-26`. Doc: `docs/gajjala/track_record_2026_10_16.md`
- **✅ wins first + row flags (2026-10-27)** — Ajay, verbatim: "Can you sort the winds in Gajjals I can't seem to tell the
  difference in that tab or show some greed flags on the wins rows" (HIS CALL Q11 answered; AMENDMENTS11 F13 reversed).
  `ledger.py` serves each row's `flag_text` (`BUCKET_TEXT` on `FLAG_BUCKETS` = win / loss rows, `None` elsewhere) and the
  block's `sorts` (`SORT_KEYS` wins · rang, `SORT_LABELS`, `SORT_BY_BUCKET`), `sort_param` (`SORT_PARAM` "sort"),
  `sort_default` ("wins") and `bucket_order` (`BUCKETS`); the server NEVER reorders a row. The FE (`ggTrSort` /
  `ggSortRows` / `ggTrRowClass`, `GgTrSorts`) sorts each served day client-side over the served order, draws the served
  flag in the Ticker cell, tints rows by their served bucket, and keeps `sort` off the 🏁 GET. The 🚩 lane rows take the
  same tint from the sign of their closed `pnl_usd`. Contracts: "✅ wins first + row flags on the 🏁 Track record
  (2026-10-27)"; ✨ `chart-maps-gajjala-wins-sort-flags-2026-10-27`. Doc: `docs/gajjala/track_record_2026_10_16.md`
  § "✅ wins first + row flags (2026-10-27)". UNMEASURED.
  "🎯 A+ filter + the win/loss charts (2026-10-26)".
- **🏁 Gajjala's three Track records read alike (2026-11-05)** — Ajay, verbatim: "Can you make both Gajjala's track
  record and Gajjalas 1 min and Gajjalas AUDIT HAVE similar track record." and "its hard to tell which ones won in
  Gajjlas Audit page". The 🧪 🏁 listed only an A+ that passed every ON rule (none since 2026-11-01), so its page showed
  count tables and no ticker. Now the 🧪 🏁 = `ledger.served_block` over the SHARED store (🚩's own A+ rows for the
  🧪 record's sessions, the ONE ledger's ✅/❌, dedupe, charts, Tape) plus ONE served `audit` cell per row
  (`audited_tab.track_block` / `row_audits` / `_audit_cell`; words `variant.WORDS_GGA` `row_audit_*` / `row_exit_*`:
  passed every rule · held by {ids} · not judged · not read; T3 / T5 exit words as sub_text where served). The audit is
  read ONCE per GET in `tab.py` and handed to both the rows and the compare; a failed read leaves 🚩's rows listed with
  NOT_READ cells (compare absent); the 🧪 route does no live today read (`today=None`, HIS CALL #28). The 1-minute 🏁
  measured no drift from 🚩's shape — PINNED (`tests/test_gajjala_track_parity_2026_11_05.py`, every `LEDGER_SPANS`
  value). FE: `GgTrRow.audit`, rows mount before the compare tables, `ggAudited.css` state hooks, `gajjala.css` ≤ 430 px
  Ticker-cell wrap. ✅/❌, categories and charts on 🧪 stay 🚩's grade of the original (HIS CALL #32); 🧠 rows not
  listed on 🧪 (HIS CALL #26). No GG5 / GG1 fixture byte moved; no grade, gate, rule, threshold, claim or push changed.
  ✨ `chart-maps-gajjala-track-records-alike-2026-11-05`. Docs: `docs/gajjala/audited_modifications_2026_11_01.md`
  § "🏁 rows on the 🧪 Track record (2026-11-05)", `docs/gajjala/one_minute_page_2026_10_27.md` § "🏁 parity with 🚩's
  5-minute 🏁 (2026-11-05)". UNMEASURED.
- **🔁 One count per stock per day (2026-11-02)** — Ajay, verbatim: "make sure you are not accounting for duplicates of
  the same stock as winner unless it did the same pattern again and met all the criteria on the same day". ONE pure
  engine `ledger.dedupe_trades` over `ledger.trade_facts`, partition `dup_group` = (date, symbol, count line); the first
  ring counts; a later ring is a duplicate on (a) the same fill minute, (b) the same trigger and stop, (c) a trade held
  while the first was running (a filled later ring judged by its fill — its own when over before the first filled; an
  unfilled one by its ring). Duplicates stay listed (`dup_of`, `dup_text` 🔁 chip), lose the ✅/❌ flag, leave every
  count, %, chart and bucket chip (📋 all counts every row); `dup_counts`, `aplus.n_dup`, a count-line tail, his rule in
  `HONESTY` / `rule_text` / `APLUS_HONESTY`. No grade, gate or claim moves. Tests:
  `tests/test_gajjala_ledger_dedupe_2026_11_02.py`. Doc: `docs/gajjala/track_record_2026_10_16.md` § "🔁 One count per
  stock per day (2026-11-02)". UNMEASURED.
- **📈 Tape column on the 🏁 list (2026-10-29)** — Ajay, verbatim: "I wanna see this kind of graph in our Track record
  page this screenshot is from Promo circuit page." `tape.py` `parse_id` also reads a 🧠 id (`…|potential`, kind
  `LG.KINDS[0]`; `kind_of` names it); the 🧠 tape is the A+ build over the ledger's own 🧠 row and its stored grades —
  the ring at the first-seen bar, trigger / stop / +1R, the fill dot when graded entered, the exit dot — in its own
  words (`ENTRY_TAPE_WORDS` `pot_*` = `POTENTIAL_TAPE_KEYS`); a no_risk / no_plan 🧠 row draws the bars and the ring
  only with the served `LG.NO_RISK_TEXT` / `NO_PLAN_TEXT` sentence. Both routes (GG5 + `gajjala-1m`, 1-minute bars);
  the mini never fetches; memo per id × lite. Every A+ payload byte-identical (sha256 pin), no new served key, goldens
  unmoved. FE: the 📋 list draws the TAPE column second (after Ticker) on every row with an `id`. Tests:
  `tests/test_gajjala_tape_potential_2026_10_29.py`. Doc: `docs/gajjala/track_record_2026_10_16.md` § "📈 Tape column
  on the list (2026-10-29)". UNMEASURED.

### Chart Maps — 📌 Tracked traders — `traders/` (2026-09-12; algo888 2026-10-27)
Public traders' posts on the 📌 tab (`GntBoard`, `TRADER_TABS` == `traders/registry.py` `TRADERS` keys in order;
`DEFAULT_KEY` "gnt"). Their posts, NOT advice and NOT a portfolio (`registry.DISCLAIMER`, one sentence for every
surface). **UNMEASURED** — no study in this app has read any tracked account's names.
- **Registry** (`traders/registry.py`): gnt (Tito Adhikary, X), martinluk (Martin Luk, X), algo888 (StockTwits,
  2026-10-27). Each row: `source` ("x" | "stocktwits"), `profile_url`, `usic` (a cited championship claim or None — a
  claim-less account never serves GnT's), `gajjala` (feeds 🚩 Gajjala's list), `curate` (feeds the 08:00 curator into
  `full`; algo888 `False` — AMENDMENT A1, HIS CALL #7), `style`, and for algo888 a cited `profile` + his own words.
- **Readers** (`traders/feed.py`): x = `fetch` (x.com Relay record + key stream, syndication top posts; the
  2026-10-22 restoration); stocktwits = `fetch_stocktwits` → `parse_stocktwits` over
  `stocktwits_client.fetch_user_stream` (`USER_URL`, the same page walk as `fetch_stream` via `_walk`;
  `TRADER_ST_PAGES` 2 pages per cron read; his own messages only — reshared inner messages never read; HTML entities
  unescaped; `sentiment` = his own `entities.sentiment.basic` word or None). `refresh` dispatches on `source`; the x
  path is byte-identical. Posts in Mongo `gnt_posts` (`_id` = post id, "st…" for StockTwits); every run's verdict in
  `trader_feed_status` (with `source`), served as `refresh.note` in the account's own words (`refresh_note(…, source)`).
- **Board** (`GET /traders/{key}`): `board()` serves `source`, `source_text`, `claim_text` (None without a claim),
  `profile`, `gajjala_text` (flagged accounts only), `usic` with no fallback; the FE prints served values only.
- **Schedule** (host-mounted crontab, unchanged): `40 7,17 * * * … traders.feed refresh` (exit 1 = PARTIAL, 2 = an
  account stored nothing) and `0 8 * * * … traders.curate`; the 🚩 Gajjala pass also re-reads a flagged StockTwits
  account (`TRADER_REFRESH_SEC`).
- **Docs** `backend/docs/traders/gnt.md` (+ "## 2026-10-27 — algo888 on StockTwits"),
  `docs/gajjala/trader_names_2026_10_27.md`; contracts "📌 GnT: latest-posts source restored + served verdict
  (2026-10-22)" and "📌 algo888 tracked + his names into Gajjala's scan (2026-10-27)".

### Chart Maps — 🚩 Gajjala's 1-minute page — `chart_maps/gajjala/variant.py` (2026-10-27)
Ajay 2026-10-27: *"Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min candles
please."* and *"do everything and also add the track record for it from today.."* (BUILD_SPEC27). Tab `gajjala_1m`, right
after 🚩 Gajjala's, label `GG1M_TAB_LABEL`. **UNMEASURED** — nothing has measured a 1-minute read; the 2026-10-14 study of
the 5-minute setups read NULL.
- **One pipeline, a frozen `Variant`** (`variant.py`): `GG5` = 🚩 Gajjala's (every stored and served byte unchanged —
  `tests/test_gajjala_variant_gg5_identity.py` + the three goldens); `GG1` = the same detectors / alerts / potentials /
  ledger / tape / board on CLOSED `("1m", "5m")` frames (the ➖ Fade on 5-minute first), claims `GG1:`, kinds
  `gajjala_1m_setup` / `gajjala_1m_potential`, api base `/chart-maps/gajjala-1m`. Words: `WORDS_1M` (served as the board's
  `variant` block: title, honesty, tfs, record_from); the FE types none.
- **Collections** (`store.OWN` / `store.SHARED`): GG1 writes only `gajjala_1m_*` (passes, reads, alerts, state,
  potentials, ledger, replay) and reads GG5's scan, ah-carry, post, halts, daily and the ONE broker-list doc. GG1 never
  scans: names = GG5's listed names, capped at `GG1M_MAX_NAMES` by today's change; ctx = GG5's stored ctx.
- **Cadence** (`run_1m.py`): the 🚩 cron pass's `run.main` SPAWNS a detached `run_1m --loop` (`spawn_loop`; cron path only)
  and returns at once — never in-process (supercronic runs without `-overlapping` and would SKIP the next 🚩 tick). The
  loop reads one closed 1-minute bar per iteration, at most 5 per slot, inside `GG1M_MINUTE_BUDGET_SEC` +
  `GG1M_SLOT_MARGIN_SEC`; its own lease (`GG1M_LEASE_SEC`). No crontab line. Kill switch `GAJJALA_1M_ENABLED` / env
  `GAJJALA_1M_ENABLED=0`. Nightly grades GG1 after GG5 (fenced).
- **Live since 2026-10-29** (was Shadow 2026-10-27 … 2026-10-28): `GAJJALA_1M_PUSH_MODE` = "live" — Ajay: "Only give me
  Gajjalas chart notifications from both tabs, / I am missing out the ones in noise." (HIS CALL #1 answered). Both kinds
  default_prefs False for everyone else, ON for the owner through OWNER_KEEP_SET (exactly six 2026-10-29 … 2026-11-01:
  gajjala_setup, gajjala_potential, gajjala_1m_setup, gajjala_1m_potential, position_alert, ops_alert; seven since
  2026-11-01 — `luk_setup`). The shadow-key guard stays (a
  key shadowed earlier the same day never rings after the flip). The 🏁 Track record counts the 🧠 potentials (shadow
  and sent) and the A+ from `GG1M_RECORD_FROM` (2026-10-27) — no replay, no backfill; each 🧠 row's kind word is read
  from its own push state. The served words follow the mode (`variant.WORDS_1M` / `WORDS_1M_SHADOW`).
- **Routes**: `GET /chart-maps/gajjala-1m`, `POST /chart-maps/gajjala-1m/scan` (owner; stealth 404),
  `GET /chart-maps/gajjala-1m/entry-tape` (1-minute bars, up to `GG1M_TAPE_BARS_MAX`). Broker flags stay under
  `/chart-maps/gajjala/…`.
- **FE**: `GajjalaBoard variant="gajjala_1m"` mounted with `key="gajjala_1m"` (the remount); `components/ggVariant.ts`
  `GG_VARIANT_BASE` == variant.py `api_base`.
- Doc `docs/gajjala/one_minute_page_2026_10_27.md` (the 15 HIS CALLs, costs, verification); contract "🚩 Gajjala
  1-minute page (2026-10-27)"; ✨ `chart-maps-gajjala-1m-2026-10-27`.
- **🧪 Entry zone on the 1-minute cards (2026-11-08)** — Ajay, verbatim: "On the Gajjalas Audited and Gajjalas 1 min tab
  can you add entry signal on the chart please like a small zone. Based on what he said, Like when its imminent with
  volume drying and selling pressure is low. and Also when the pullback is ideal and close EMAs I guess based on what he
  says." `chart_maps/gajjala/entry_zone.py`, called once from `tab.setup_tile` on the STORED read (it carries `base`):
  ONE served band `{kind: "gg_entry", lo: stop, hi: trigger, label: WORDS_1M["zone_label"] = "entry zone", note:
  WORDS_1M["zone_note"] = "{why} · UNMEASURED"}` on a FORMING setup card (🧠 tiles included) when IMMINENT (`ready` True
  AND `context.red_closes_chip(red_closes)` is None — GG S11 "The volume will dry up during the entries of all my
  setups", GG X 1733882105204011109 "more than 3 red closes is red flag to me") and/or IDEAL PULLBACK (`k3_vol` ✓ AND the
  setup's own EMA criterion ✓: 💋 `k5a_honor` · 🌀 `k7_ema21` · ➖ `k6_merge`; 🚩 and 🎾 have no EMA rule → imminent
  only); guards: a base of ≥ 1 bar (K3 is vacuous over an empty pullback) and `ledger.plan_of` = ok. Built from the
  criteria already on the read — no new number, no new rule; never on partial / A+ / triggered / stopped (his 11-06
  "keep it": no EMA exit word). FE: `PatternChart` `BAND_FILL` / `BAND_NAME` `gg_entry` (gold), `CmBand.note?`, the card
  line prints the served `note` verbatim (`GajjalaBoard` `gg-zone-<SYM>`). The 1-minute FE golden gained exactly two
  bands (the GGB bull_flag card and its 🧠 tile, `red_closes` 3 = the boundary). Doc
  `docs/gajjala/entry_zones_2026_11_08.md` (HIS CALLs #1–#5, #11); contract "🧪 entry zones · 🎾 SI label · ➖ EMA rank
  (2026-11-08)"; ✨ `chart-maps-gajjala-entry-zones-2026-11-08` (routed to the 🧪 tab). UNMEASURED. Not advice.

### Chart Maps — 🧪 Gajjala · Audited — `chart_maps/gajjala/audited_rules.py` (2026-11-01)
Ajay 2026-11-01: *"I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited  So we can keep track of improvements on this tab"* (BUILD_SPEC gg-audited). Tab `gajjala_audited`, right
after 🚩 Gajjala's, label `GGA_TAB_LABEL`. **UNMEASURED.** Every rule read TOO SMALL in the 2026-10-30 replay (LEDGER.md
rows 2026-10-30). **Shadow only.** Every audited alert is recorded and never sent.
- **An overlay, not a pipeline.** Variant `GGA` (`variant.py`, claims `GGA:`) has no scan, no cron line and no provider
  call. A fenced step inside 🚩's 5-minute pass (`audited_pass.run_step`) does three things:
  - It judges each GG5 **A+** read against the ON registry rules on the same Frames.
  - It hands the survivors to `alerts.run_pass(…, mode="shadow")` on the audited store.
  - It serves a removed A+ as `aplus_held` ("A+ on the original, held here by the audit"). It is never hidden.

  GG5 and GG1 stay byte-identical: no key is added to `out` or to the pass doc, and the three goldens are not
  regenerated.
- **Registry** (`audited_rules.py`, `REGISTRY`, `AUDIT_VERSION`). The numbers come from the frozen prereg
  (`eod-audits/research/2026-10-30_gajjala_gates_prereg.md`, sha `4ebc30d2…14b6`) and the ported study gate math (sha
  `20bb1970…2798`, byte copies under `tests/fixtures/gajjala/`).
  - **G1** break-bar proof (ON, `G1_K`)
  - **G2** red closes (ON, `G2_MAX_RED` = `RED_CLOSES_WAIT`, `G2_RUN` "last" = the prereg; the replay read "longest", HIS CALL)
  - **G3** ring age (lane_only, applied nowhere)
  - **G4** stop-distance cap (ON, `G4_MAX_RISK_PCT`; on 🎾 the stop is frozen at the first armed read)

  G1 and G2 are judged on the read's own frame, which is 15-minute for the Horizontal Fade (HIS CALL #14). The rules
  fail closed.
- **The process for a future audit.** An audit-derived modification becomes a registry entry with its eod-audits source.
  It stays OFF until his call, then goes ON on this tab only. The 🚩 tab is never the target. A verdict is a LEDGER row
  plus a `verdict` update. The words never flip on a count (`floor_reached`, `MEASURE_FLOOR_WEEKS`).
- **Collections.** GGA writes only `gajjala_audited_overlay` (names with an A+ or an armed 🎾, TTL `READS_TTL_DAYS`),
  `gajjala_audited_alerts`, `gajjala_audited_state` (`audit_latest`) and `gajjala_audited_ledger`. It borrows GG5's
  reads, potentials, passes and replay (`Variant.borrows`).
- **Costs.**
  - The pass makes zero provider calls (a counter test).
  - The nightly (`nightly.grade_audited`, after GG5 → GG1) COPIES GG5's graded columns when id, stamp, trigger, stop and
    plan match (`copied_from: "gajjala_ledger"` inside the column). It then runs `grade_step` for the RESIDUAL only,
    bounded by `LEDGER_BACKFILL_MAX_SYMBOL_DAYS` and served as `gajjala_audited.copy.residual`.
- **Pushes.** None. The two locks are `GAJJALA_AUDITED_PUSH_MODE = "shadow"` and the explicit `mode="shadow"`. The
  variant has no sender (`NEVER_SENDS`), no push/subs kind, and `OWNER_KEEP_SET` stays six. `/alerts` shows one
  PASS-HEALTH row (`gajjala_audited_setup`) under its own "never sent" eyebrow.
- **Board** (`tab.build(…, variant=GGA)`, `audited_tab.py`). It serves these keys:
  - `audited`: the strip, with the registry, pass line, stale and `unaudited`
  - `held`: the held-A+ section
  - `audited_compare` on 🏁: original vs audited vs held on the same sessions and trade math, plus `recon`, `by_rule`
    (with `by_rule_note`), `by_day` and `floor_reached`
  - `counts.aplus_held`
  - the tile's `gajjala.audit`

  🏁 starts at `GGA_RECORD_FROM` (2026-11-01).
- **Routes.**
  - `GET /chart-maps/gajjala-audited`. On 🏁 only, `today_read` runs over `ST.for_variant(GGA)`.
  - `POST /chart-maps/gajjala-audited/scan`: owner-only, stealth 404. It calls `on_demand.request()` with NO variant,
    which is 🚩's on-open pass; the overlay rides it.
  - `GET /chart-maps/gajjala-audited/entry-tape` reads the audited store.
- **ℹ️ panel.** `rules_info._gg_audited_clause()` = `" " + audited_rules.rules_clause()`, placed after the one-minute
  clause. Its source holds no numeric literal.
- **FE.** `GajjalaBoard variant="gajjala_audited"` is mounted with `key="gajjala_audited"`. New components are
  `GgAuditedStrip` (folded), `GgAuditedHeld` and `GgAuditedCompare`. `GG_VARIANT_BASE` == `GGA.api_base`.
- Doc: `docs/gajjala/audited_variant_2026_11_01.md` (the registry with sources, the process, costs, recon semantics, the
  15 HIS CALLs, verification). Contract: "🧪 Gajjala · Audited tab (2026-11-01)". ✨ `chart-maps-gajjala-audited-2026-11-01`.
- **2026-11-01 modifications** (*"Yes make the changes in audited please"* / *"But keep a track record too to see the winners and loster"*): eight entries ON on 🧪 only (filters T1 T2 A1 H1 T4 A2, exit grades T3 T5; prereg `PREREG2_SHA256`, `AUDIT_VERSION` 2), judged only on the bars 🚩 would ring (`alerts.refusal`), a per-rule winners/losers table on the 🧪 🏁 (`per_rule`, replaces `by_rule`), exit grades one night later from warm cache only (`gajjala_audited_exits`, 0 provider calls); UNMEASURED, shadow; doc `docs/gajjala/audited_modifications_2026_11_01.md` (HIS CALLs #16–#25).
- **🔁 One count per stock per day (2026-11-02)** on the 🧪 🏁: each side dedupes over its own rows with the ledger's
  engine; the held side over its own rows from the ORIGINALS' facts (never inherited); a duplicate original is never
  rule-scored; `_tally` drops duplicates (`n_dup` served); identity `o.n + o.n_dup == a.n + a.n_dup + held.n + held.n_dup
  + original_only − audited_only − both`. Doc `docs/gajjala/audited_modifications_2026_11_01.md` § Attribution.
- **🧪 Entry zone on the Audited cards (2026-11-08)** — the same `entry_zone.bands(read, v)` over the 🧪 cards (GG5's
  5-minute reads overlaid): the words are `WORDS_GGA["zone_label"]` / `["zone_note"]`; a held A+ (`aplus_held`) is not
  forming, so it carries no band; GG5 has no word, so `variant.word` is None and its cards serve `bands: []` byte for
  byte (`test_gajjala_variant_gg5_identity.py`). Same doc, contract and ✨ as the 1-minute page's entry. UNMEASURED.
- **🧪 K3S — K3 volume-dry not binding on the 🎾 base (2026-11-09)** (*"yes change the audit as per you like that is yours
  I need you to make it successful and earn money that is the goal"*): a third registry KIND, `KIND_ADMIT`, ON on 🧪 only
  (`REGISTRY` 13 ids, K3S last; prereg `PREREG3_SHA256` be966681e317…, `tests/fixtures/gajjala/audited_k3s_prereg_2026_11_09.md`;
  `AUDIT_VERSION` 3). A 🚩 `reversal_squeeze` read that broke "partial" with `missed` exactly `["k3_vol"]` is re-read ON ITS
  BREAK BAR through the ONE detector (`detectors.reversal_squeeze(..., k3_binding=False)`; the default True = 🚩's bytes),
  K11 re-applied with the pass's own session volume (fail-closed), then handed through the same refusal chain, `judge(...,
  admit="K3S")`, T1, shadow claim and `#held` marker as any 🚩 A+ — inside `audited_pass.run_step` only. 🚩's own plan;
  no new number; `K3_VOL_FRAC` untouched; GG5 byte-identical; pushes SHADOW; `OWNER_KEEP_SET` seven. Every 🎾 partial
  break leaves one first-wins `#partial_break` row (never a 🏁 row, never a claim) for the prereg's placebo. The audit
  block gains `admit` (None on every non-K3S block); the compare block gains `admitted` ("🧪 only": W / L / filled /
  mean R / held-by / same-day original) and `recon.admitted`; the per-rule table gains a K3S row. The card prints the
  audit's words through the served `state_label` on the break pass only. Doc `docs/gajjala/audited_k3s_2026_11_09.md`
  (HIS CALLs #37–#49); LEDGER.md row '🧪 K3S' 2026-11-09; contract "🧪 K3S (2026-11-09)"; ✨
  `chart-maps-gajjala-audited-k3s-2026-11-09`. UNMEASURED — n ≥ 30 rings before any word. Not advice.
- **⏱ Gajjala live — feed word · lane stream (SHADOW) · bar-close probe · tab live · latency ledger (2026-11-09)**
  (*"I would like the autopilot to be continously monitored or live tracked and changed as if Gallalas makes the trades can
  you modify and make it more live with websockets or something else where there is a low latency monitoring on the prices
  action changes please?"* / *"same for reuglar Gajjlas tab as well need it to be more live"*; spec gg_live rev 2, WP-A..E +
  Z). No rule, gate, push kind or pass time moved: the A+ is still the 5-minute bar CLOSED through the trigger. Shipped:
  **(P0)** the ONE Massive socket made honest — kick timeline (`live_feed_events`, TTL 14 d), `GET /live/feed-status` serves
  `state` + `word` (`live_feed.FEED_WORDS`) and, admins only, `admin_word` + `?events=1`, every string through
  `_scrub_obj` (the stocks key never leaves); /alerts prints the served word verbatim; `enabled()` refuses `auto` on
  `CHEETAH_ENV=dev`; the QuoteCache Mongo persist is coalesced (`LIVE_CACHE_PERSIST_SEC`, declared); `live_hub.py` = the ONE
  print filter (`PRINT_KINDS`) + interest keyed (variant tab, symbol) (`docs/realtime/massive_ws_feed.md`,
  `docs/realtime/socket_kick_2026_11_09.md`, canary NOT run). **(P1)** `trading/gajjala_stream.py` — stream entries, shipped in
  SHADOW at 02:29 ET and LIVE since ~10:00 ET 2026-11-09 (`GG_STREAM_MODE "live"`, HIS CALL #1 answered: "With entries
  realtime like Gajjala does"; env lowers only). In SHADOW: the first print at/over the trigger (and the first non-odd-lot one,
  and the stop) recorded insert-once in `gajjala_lane_stream` beside the 1-minute tick — zero broker calls, zero orders
  change; the lane-run mutex (`LANE_RUN_MUTEX_SEC` 55) around `run()` and `run_stream()`; `status_block.stream` word on
  /trading?view=gajjala (`docs/trading_gajjala_lane.md` "Stream entries (shadow)"). **(P2)** `chart_maps/gajjala/bar_close.py`
  — a finality PROBE (`GAJJALA_BAR_CLOSE_MODE "probe"`, `GAJJALA_BAR_FINAL_PROBE_SESSIONS` 5): a detached child per cron slot
  reads the closed 5-minute bar at close + 30 s and + 60 s into `gajjala_bar_final`; no lease, no pass, no push; the pass
  stays on `:x1` (`docs/gajjala/bar_close_pass_2026_11_09.md`). **(P3)** the 🚩 / 1-minute / 🧪 boards live over the
  existing `/events` bus — one event `gajjala.update` (`chart_maps/gajjala/live_events.py`; quotes ≤ 1 batch/s per variant,
  `pass` and data-free `lane` nudges coalesced 500 ms); `POST /chart-maps/live` with `stream: true` registers interest and
  is byte-identical without it; the 30 s card poll stays as the bar splice + fallback; the feed word prints only when
  degraded (`docs/gajjala/live_tab_2026_11_09.md`). **(P4)** the ⏱ latency ledger — `GET /trading/gajjala/latency?span=`
  (owner only) = `chart_maps/gajjala/latency.payload` = `scripts/gajjala_latency_report.py`; mounted under the A+ charts on
  the 🏁 (`<GajjalaLatency span={tr.span} />`); split at `latency.GG_LIVE_FROM` = 2026-11-09 (MINE: deployed ~02:30 ET 11-09,
  the first full session on the new code); measured "before" (n 47 pushed live `GG:` A+ since 2026-10-01, p50 s after close): Read 61.0 · Rang
  70.6 · Lane saw 122.0 · Ordered 124.0 · Filled 127.0 (`docs/gajjala/latency_ledger_2026_11_09.md`).
  **Does NOT change** (spec §3.9): `detectors.py` and every read (GG5 goldens + `gg5_{writes,board}_2026_10_27.json`
  byte-identical); the pass timing (`:x1`); `alerts.py` gates, claim keys, `MAX_ENTRY_AGE_SEC`; `OWNER_KEEP_SET` (seven)
  and every push kind; `BAR_SETTLE_SEC`, `PASS_CADENCE_SEC`, `PASS_BUDGET_SEC`, `LEASE_SEC`, `LEASE_MIN_GAP_SEC`,
  `PASS_MINUTE_OFFSET`; the crontab; the lane rules and numbers (`GAJJALA_RISK_PCT`, `GG_BE_AFTER_BARS`, trail EMAs,
  flatten / cut-off, `WINDOW_OPEN_ET`, `GAJJALA_MAX_OPEN`, `GAJJALA_FILL_WAIT_SEC`, `GAJJALA_MISSED_R`, floors); paper-only;
  regular-hours lane; `run_1m.slot_of` / `fits`, Luk, the 🧪 overlay; `quote.update` (0.5 s) and the QuoteCache payload;
  `SSE_HEADERS` and the six SSE endpoints; the 🏁 payload and its three goldens; Finnhub off; no AM, no new Q;
  `_RECONNECT_COOLDOWN`'s default. **Known gap:** `gajjala.update` reaches every signed-in tab (public prices + data-free
  nudges); owner-only delivery needs a bus change (HIS CALL #16).
  **HIS CALLs** (spec §7; built default in brackets): **#1** stream entries LIVE? [SHADOW] · **#2** which prints count as
  "traded the trigger" — odd lots (37), Form T (12) [`"regular"` incl. both; `trigger_lot` rows record the round-lot
  variant] · **#3** intrabar vs closed-bar lane entry [closed — the pushed A+ only] · **#4** extended-hours lane [unchanged,
  regular hours 09:45–15:30] · **#5** the early pass ON at close + 30 s? [probe, 5 sessions] · **#6** `BAR_SETTLE_SEC` 30 s
  [unchanged] · **#7** where P2 runs [cron container, detached child] · **#8** where P1 places orders [api hub worker, same
  lane code, the mutex] · **#9** discovery cadence [inside the 5-minute pass] · **#10** post-kick policy + running the canary
  [`MASSIVE_WS_KICK_COOLDOWN_SEC` 30 s, yield guard OFF, canary NOT run] · **#11** second-client suspects he can check
  [listed in the socket doc] · **#12** rotate the stocks key [not done — his dashboard step] · **#13** plan check if
  `lag_ms_p50` ≈ 900 s [nothing bought] · **#14** latency targets [proposed in the ledger doc, not adopted] · **#15** the
  30 s card poll [kept as splice + fallback] · **#16** household broadcast of `gajjala.update` [every signed-in tab; he asked
  owner-only — needs a bus change] · **#17** bar-close lane management by the hub [LIVE only, part of #1] · **#18** hot
  mini-pass for armed 🧠 names [not built] · **#19** feed word placement [/alerts always; boards + lane tab only when
  degraded]. Contract "⏱ Gajjala live: feed word · lane stream (shadow) · bar-close probe · tab live · latency ledger
  (2026-11-09)"; ✨ `chart-maps-gajjala-live-stream-2026-11-09`. UNMEASURED — a timing, not a result. Paper only. Not advice.

### Chart Maps — 🥇 Luk's tab — `chart_maps/luk/` (2026-11-01)
Ajay 2026-11-01: *"look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources. ... I need something like Gajjlala that is exposed"*. Martin Luk:
USIC $20k+ Stock 2025 winner (+969.8%), 2026 leader (+785.8% through Sep 30), 2024 6th (+283.1%); he sells nothing and
every rule is his own words in free sources. Tab `luk`, right after `gajjala_1m`, before `doji_sweep`, label
`LUK_TAB_LABEL`. **UNMEASURED. Shadow only** — every alert is recorded and never sent.
- **Its own package, GG's generic primitives by import.** `Variant` instance `LUK` (`luk/variant.py`, claims `LUK:`,
  never in GG's registry; `gajjala.variant.push_mode(LUK)` fails closed to "shadow"). `LukStore(GajjalaStore)` writes
  only `luk_passes`, `luk_reads`, `luk_alerts`, `luk_state`, `luk_ledger`, `luk_daily`, `luk_screens`; every other GG
  collection is a refusing stub; the lease numbers are Luk's own. Frames `1m · 5m · 60m` (60m = regular-session minutes,
  clock-anchored; its ema9/ema21 are his hourly 9/21).
- **Numbers = constants.** `chart_maps/luk/constants.py` is the ONLY number source; every line is tagged `LUK
  <file>:<line> [ts]` (his words, byte copies under `tests/fixtures/luk/`, sha256-pinned), `LUK substack`, `LUK frame
  U4/U5/U6`, `MINE (HIS CALL #n)`, `derived` or `EXTERNAL`. GG numbers are imported from `gajjala.constants`, never
  retyped. `verified_rules.json` = the rules with sources and verbatim quotes (found at the cited line ±2).
- **Screens** (`screens.py`): ☀️ Pre-market, 🏆 Leader, ⚡ Potent — his TradingView frames, STRICT comparisons, top
  `LUK_SCREEN_TOP_N` each; formulas for 1-week volatility / price×volume / 1-month % / ADR (`sepa.adr`, 20 sessions) are
  MINE. Cap unknown → kept, "cap unknown — not filtered". Closed daily bars only through Luk's OWN post-close
  fetch (`load_prices(force=True)` at or after d 16:00 ET + `LUK_DAILY_TRUST_AFTER_SEC`, stored in `luk_daily`; the house
  cache is never a close proof — `patch_latest_closes` re-stamps it), ≤ `LUK_DAILY_MAX_NEW_PER_PASS` new names per pass,
  the rest "daily facts pending"; the QQQ/IWM words the same way once per session (`LUK_STATE_INDEX`).
- **Setups** (`detectors.py`): ↩️ `pullback_reversal` (daily-9 pullback + a 5-minute low at the hourly 9 EMA, then the
  first previous-bar-high break, never on the way down; 1-minute closes ≤ 09:45, 5-minute to 10:30), 🔔
  `opening_range_high` (the 09:30 1-minute candle's high; 1-minute until 09:35, then 5-minute; 60 minutes), 📦
  `inside_day_pdh` (strict inside day, prior-day high, any regular-session time). Stop: LOD; entry-to-LOD >
  `LUK_LOD_SWITCH_PCT` → the 5-minute entry candle low; wider than `LUK_STOP_MAX_PCT` or half the 20-day ADR → `listed`;
  > `LUK_NO_CHASE_PCT` above the LOD → `listed`. Every lookback through the break bar. A+ per frame: 5-minute = GG's
  latest-closed-bar rule; 1-minute = closed after the previous pass's `LUK_STATE_BARS_THROUGH`, no stop touch since.
  Market state (QQQ, IWM 9 vs 21 EMA) = a word, never a gate.
- **Pass / costs.** ONE edit to the gajjala package: `_spawn_luk()` in `gajjala/run.py`, called right after
  `_spawn_1m()` on the cron path only, spawns `python -m chart_maps.luk.run --child` DETACHED when `enabled()` and
  `in_window()` (04:00–16:05 ET); fenced, never changes the exit code; pinned STRUCTURALLY
  (`tests/test_luk_gajjala_hook.py`). Kill switch `LUK_ENABLED` / env `LUK_ENABLED=0` (conftest assigns "0"). Per pass:
  1 snapshot + ≤ 8 daily fetches + ≤ 40 today-minute fetches + first-appearance prior-session loads + ≤ 60 grade loads;
  ≈ 145 passes/day → worst case ≈ 7.1k calls/day + the measured prior loads; budget 120 s inside the 300 s slot
  (`fits()`).
- **Pushes: LIVE since 2026-11-01** (Ajay: "Lets make it live. also alerts too." — HIS CALL #19 answered):
  `LUK_PUSH_MODE` = "live", kind `luk_setup` (push/subs default False, OWNER_KEEP_SET seventh kind,
  hooks.notify_luk_setup, a MARKET kind), the LUK Variant's `send_setup`; the live branch of `luk/alerts.run_pass` =
  GG's (shadow-key guard, one claim per session/symbol/setup, pushed / no_target / failed settled); shadow = the
  fail-closed fallback. `/alerts` row `luk_setup` beside the 🚩 1-minute block. The 🏁 grades pushed and shadow rows,
  each row's own line says which.
- **🏁 Track record** (`ledger.py`, graded inside the Luk pass, from `LUK_RECORD_FROM` 2026-11-01): fill = the first
  1-minute bar ≥ 30 s after the alert at or above the trigger, from 09:30, same session; exit = the stop (−1.0R) or the
  first daily close below the daily 9 EMA; 3R / 5R flags only; no max hold. Closed days only via `daily.closed_through`
  (trusted row or one counted fetch; else deferred and retried). Operational accounting, not a backtest.
  **2026-11-02**: one count per stock per day (Ajay: "make sure you are not accounting for duplicates of the same stock
  as winner unless it did the same pattern again and met all the criteria on the same day") — the 🥇 ledger's adapter
  feeds `gajjala.ledger.dedupe_trades` (partition date / symbol / line); a duplicate is listed and chipped 🔁, never
  counted; the 🏁 serves 🚩's shape (heads, views, categories, sorts, charts) through the shared components.
- **Board keys** (`tab.build`): `tab, label, title, honesty, variant, session, pass, strip (folded: market_state,
  push/record/external/cost/latency), subs (eight: ↩️ 🔔 📦 ☀️ 🏆 ⚡ 📓 🏁), sub, counts, counts_text, counts_legend,
  tiles, screens, playbook, track_record`. The 📓 Playbook serves every rule with its cite, the SYNTHESIS §D HIS CALLs
  and the external backtests as EXTERNAL.
- **Routes**: `GET /chart-maps/luk?sub=&span=&focus=&limit=`, `GET /chart-maps/luk/entry-tape?id=&lite=`,
  `POST /chart-maps/luk/scan` (owner's 🔄 scan now, 2026-11-11; stealth 404 for anyone else).
- **ℹ️ panel**: section "🥇 Luk's" = `luk.playbook.rules_lines()`, before "doji_sweep"; fenced; no numeric literal in
  `rules_info.py`.
- **FE**: `LukBoard` (+ `LukCard` drawing `PatternChart`, `LukScreens`, `LukPlaybook`, `LukTrackRecord` (🚩's shared 🏁 row; 📈 opens
  `GgEntryTape` on the Luk route via `GgVariantContext` 'luk' — `LukEntryTape` deleted 2026-11-02), `LukStrip`, `styles/luk.css`); `lib/luk.ts` `LUK_BASE` ==
  `variant.LUK.api_base`; the FE composes no word and no number.
- Doc `docs/luk/luk_tab_2026_11_01.md` (every rule with its cite, screens and formulas, states, stop plan, 🏁 math, the
  15 SYNTHESIS HIS CALLs + 30 build HIS CALLs, cost arithmetic with the measured `calls`, external backtests, traps).
  Contract: "🥇 Luk's tab (2026-11-01)". ✨ `chart-maps-luk-2026-11-01`.

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
  default `max_429=None` keeps every other caller unchanged). Since 2026-10-18 (DECISIONS14) the trades and NBBO pulls
  run as 13 parallel ET windows (`orderflow/massive_pages.py`; `MAX_429` counts per window; up to 24 pages per trade window — the old
  whole-day cap; the NBBO uses the 11 session windows × 8 pages = `quotes.MAX_QUOTE_PAGES` 88; each page compacted as
  it arrives, D11/D12), and the quote rule
  classifies inside covered windows only (`quotes.covered_mask`); `coverage_pct` = the share of prints with a held
  quote (D10) — docs/orderflow/parallel_fetch_2026_10_18.md. "Today" = the ET day of the poll clock, never the container's.
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
- **🎚 Who's in control (2026-10-21, BUILD_SPEC21)**: `tape.delta_summary` serves `control` {session, late, turning,
  headline, detail} — the sign rule (> 0 buyers, < 0 sellers, 0 balanced; no threshold) over the session and the last
  `LATE_WINDOW_MIN` delta, words in `tape.CONTROL_TEXT`; the Tape panel prints it verbatim. UNMEASURED.
  `docs/sepa/orderflow_methodology.md` §"Who's in control (2026-10-21)".

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
  no now line gains one only when `add_line` (since 2026-11-09 the api sets `add_line` in EVERY session — Ajay: "I can't see now for them again"; before, extended hours only). Unchanged → the same tile object (PatternChart `memo`). The served footer
  word joins the existing `cm-scanstamp` freshness line ("live · HH:MM:SS ET" / "last refresh HH:MM ET") — no new chrome.
- **Budget**: one Massive snapshot call + one Mongo find per 30 s per open, visible board tab (≤ the cap); one per 30 min
  closed. No WS, no SSE, no focus-list change.
- **Contracts**: `scripts/contracts.mjs` "🔴 live card overlay (2026-10-16)". **Tests**:
  `backend/tests/test_chart_maps_live_card.py`, `frontend/src/lib/cardLive.test.ts`, `src/hooks/useCardLive.test.tsx`,
  `src/pages/ChartMapsCardLive.test.tsx`, `src/components/PatternChart.cardLive.test.tsx`.
- **HIS CALLS**: `docs/chart_maps/live_card_2026_10_16.md` (Q1–Q14 + the builders' a–d).
- **🔴 Gajjala cards live (2026-10-21, BUILD_SPEC20)**: the 🚩 tab's tiles ride this overlay; an OPTIONAL body `levels`
  {SYM: {trigger, stop, tf}} (copied from the tab payload) adds display-only `vs` {kind over_trigger|under_stop|between,
  text from `live_card.VS_TEXT`} per quote (on the broker grid; malformed levels ignored, never a 422); no module under
  `chart_maps/gajjala` or `trading` imports `live_card`. UNMEASURED. `docs/gajjala/gajjala_tab_2026_10_13.md` §🔴.

### Chart Maps — 🌙 Overnight session read (Blue Ocean) — overnight/scan.py (2026-10-19)
Every stock and ETF re-priced through the overnight session (Ajay: *"Can you do an over night scan for all the stocks
they are all growing over night"*, his StockTwits screenshot, *"These are over night check qqq for example"*, *"Massive
is what we use probably we don't have the subscription"*). **UNMEASURED** — what moved overnight, never what to buy; no
edge claimed. Home: the existing Chart Maps tab `overnight` gets two subs, **🌙 Overnight session** (default, `on_sub`)
and **Gappers** (unchanged); own params `on_sub` / `on_sort` / `on_lev`, dropped crossing the tab border.
- **Clock** (`overnight/session.py`, pure): `SESSION_OPEN_ET` 20:00 → `SESSION_CLOSE_ET` 04:00 ET, the evening before
  each trade date (Alpaca 24/5 doc). `session_for(now)` → `{open, trade_date, base_date, opens_at, closes_at,
  next_open, reason}`; open only when the ONE calendar (`market_hours.gate.closed_reason` on an aware ET noon of the trade
  date) says the trade date is a market day; `base_date = reaction.prev_market_day(trade_date)`.
- **Base**: the last regular close from `sepa.prices.market_snapshot_with_meta()`, **pinned once per session** at the
  first pass (`overnight_base`), refused after `BASE_PIN_LATEST_ET` 03:30 (snapshot reset) or when SPY carries no close.
  Prior-session % = `close / prev_day_close`, never `todaysChangePerc` (carries after-hours, measured); Alpaca's
  `dailyBar` / `prevDailyBar` are overnight bars and never the base.
- **Now** (AMENDMENTS16 A1): Alpaca `feed=overnight` snapshots in batches of `ALPACA_BATCH` 200. The live quote mid
  first — quote time ≥ the session open, age ≤ `QUOTE_FRESH_SEC` 300 (MINE), 0 < bid < ask, spread / mid ≤
  `QUOTE_SPREAD_MAX` 0.015 (MINE) → `src "q"`; else the delayed indicative trade if it printed this session → `src
  "t"` (~15 min late, measured 900–1,044 s; served `price_age_sec`, the pass median `trade_age_median_sec`); else
  dropped `no_price`. Wire symbols `symbols.for_massive` (BRK.B); errors through `broker_alpaca._scrub`.
- **Floors**: universe close ≥ `MIN_SHARE_PRICE` ($2, house) on ≥ `UNIVERSE_MIN_DOLLAR_VOL` $1M (MINE); listed rows ≥
  `BOARD_MIN_ON_DOLLAR` $25K overnight (MINE), thinner counted; `REF_SYMBOLS` SPY QQQ IWM DIA always served first.
- **Leverage** (`scan.fund_flags`, served `leveraged` bool|None + `lev_label`): parsed from the fund's own name in the
  Massive reference list (`levered_etf.fetch_reference`, its `FUND_TYPES` / `FACTOR_RE` / `SHORT_WORDS` /
  `MIN_FACTOR_EXCLUSIVE` by name); a CS is never classified; an incomplete list → None on every row. The FE types no
  rule; "Hide leveraged ETFs" (`on_lev=1`) drops True only.
- **Collections**: `overnight_base` (`_id` trade date), `overnight_reads` (`_id` `{td}T{HHMM}`, ordered by `as_of_ts`,
  never `_id`; stored only when `counts.priced > 0`; `KEEP_SESSIONS` 2), `overnight_pass` (`_id "latest"`, every pass
  that ran), `overnight_push` (the push claim). Row keys include `pct`, `on_dollar`, `prior_pct`, `src`,
  `price_age_sec`, `leveraged`, `lev_label`.
- **Route**: `GET /overnight/session?sort=&hide_lev=` (`overnight/api.py` → `asyncio.to_thread(board.board_payload)`),
  Mongo only — never Alpaca, Massive or `scan.read_once`. Keys `session`, `read`, `last_pass`, `sorts`, `lines`,
  `refresh_sec`, `disclaimer`; every sentence a `board.py` constant the FE prints verbatim
  (`components/OvernightSessionBoard.tsx`, `lib/overnightSession.ts`, `hooks/useOvernightSession.ts`); ⭐ from
  `useWatchlist`.
- **Cron**: two `python -m overnight.scan` lines (`*/10 20-23 * * 0-4`, `*/10 0-3 * * 1-5`), NOT wrapped in
  `market_hours.gate` (it reads TODAY; Sunday 20:00 would skip) — the module self-gates on the session's trade date; one
  `market_hours.gate overnight.push` line at 06:45. Host-mounted: a deploy does NOT install them (§6; the host install
  is his step).
- **Push** `overnight_movers` (`overnight/push.py`), owner-only, one per session at `SLOT_ET` 06:45 ET, never after the
  9:30 open; top `PUSH_TOP_N` 5 gainers with price ≥ $2, ≥ `PUSH_MIN_ON_DOLLAR` $250K overnight (MINE), `leveraged is
  False` (unknown fails closed) + the index line. **Ships OFF** (`default_prefs` False, NOT in `OWNER_KEEP_SET`) — he
  asked for a scan; it still runs, logs its would-be push on /alerts and records why-quiet (`DAILY_PASS_KINDS`).
- **Contracts**: `scripts/contracts.mjs` "🌙 overnight session + overnight_movers (2026-10-19)". **Tests**:
  `backend/tests/test_overnight_session.py`, `test_overnight_scan.py`, `test_overnight_board.py`,
  `test_overnight_cron.py`, `test_overnight_push.py`, `test_overnight_movers_kind.py`; FE
  `src/lib/overnightSession.test.ts`, `src/hooks/useOvernightSession.test.tsx`, `src/components/OvernightTab.test.tsx`,
  `src/components/OvernightSessionBoard.test.tsx`, `src/pages/Notifications.overnight.test.tsx`.
- **HIS CALLS** 1–17 + OPEN O1–O7: `docs/overnight/overnight_2026_10_19.md`.

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
| `*/10 20-23 * * 0-4` | `/usr/local/bin/python -m overnight.scan` | 🌙 Overnight session read, evening half (Sun–Thu 20:00–23:50 ET, 2026-10-19). NOT wrapped in `market_hours.gate` (it reads TODAY; Sunday 20:00 is a weekend) — the module self-gates on the SESSION's trade date (holiday eves closed, zero HTTP). Pins the Massive base once, re-prices the universe from Alpaca `feed=overnight`, stores `overnight_reads`. § 3 "Chart Maps — 🌙 Overnight session read". |
| `*/10 0-3 * * 1-5` | `/usr/local/bin/python -m overnight.scan` | 🌙 Overnight session read, after-midnight half (Mon–Fri 00:00–03:50 ET). Same module, same self-gate. |
| `45 6 * * 1-5` | `/usr/local/bin/python -m market_hours.gate overnight.push` | 🌙 `overnight_movers` 06:45 ET push (`overnight/push.py` `SLOT_ET`), owner-only, **ships OFF** (his call) — the pass still records why it was quiet on /alerts. |

The three 🌙 lines are host-mounted: a deploy does NOT install them. Deploy `api frontend cron` first, then the host
install block in `docs/overnight/overnight_2026_10_19.md` (Ajay's step).

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
