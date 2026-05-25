# Cheetah Market App — Architecture

**Live URL:** https://ajays-macbook-pro.tailb3dc79.ts.net
**Repo path on host:** `/Users/ajay/clinet-test/cheetah-market-app`
**Host:** Mac book pro M5 (this machine) (Apple Silicon), behind Tailscale Funnel
**Last refreshed:** 2026-05-06

A self-hosted equity research dashboard. Mark Minervini's SEPA pipeline, Schaeffer's SOIR options pulse, overnight movers, morning brief, watchlist, push notifications — running on one Mac book pro M5 (this machine) under a Google-OAuth gate.

---

## 1. 30-second mental model

```
                   Internet
                      │
               Tailscale Funnel
        (ajays-macbook-pro.tailb3dc79.ts.net)
                      │
                      ▼
          ┌───────────────────────┐
          │   nginx (frontend)    │  port 5173 → :80 in container
          │  - serves SPA         │
          │  - auth_request gate  │
          │  - /api/* reverse pxy │
          └───────────┬───────────┘
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
 oauth2-proxy     FastAPI api    websocket /ws
 (Google login,   (port 8000)    (Finnhub stream)
  email allowlist)
                      │
              ┌───────┼───────┐
              ▼       ▼       ▼
          MongoDB  cron    cheetah-scans
         (mongo:7) (super- (shared volume
                   cronic)   for scan JSON)
```

Every request — SPA or API — goes through `oauth2-proxy`. Email must be in `backend/oauth2-emails.txt`. After login, nginx injects `X-User-Email` into every `/api/*` call so the backend can scope per-user data.

---

## 2. Deployment topology

### Containers (`docker-compose.yml`)

| Service | Image | Role | Ports | Volumes |
|---|---|---|---|---|
| `mongo` | `mongo:7` | All persistent state | `127.0.0.1:27017` (loopback only) | `mongo-data` |
| `api` | `cheetah-api:latest` (built from `backend/`) | FastAPI app, all REST + SSE endpoints | `8000` | `cheetah-scans` |
| `cron` | `cheetah-api:latest` (same image, different command) | supercronic running scheduled jobs | — | `cheetah-scans`, `./backend/crontab:ro` |
| `frontend` | `cheetah-frontend:latest` (built from `frontend/`) | nginx + built React SPA | `5173 → :80` | — |
| `oauth2-proxy` | `quay.io/oauth2-proxy/oauth2-proxy:v7.7.1` | Google OAuth gate | `127.0.0.1:4180` | `oauth2-emails.txt:ro` |

Key compose details:
- `cron` uses `init: true` because supercronic's subreaper-child re-exec fails on the Apple Silicon Docker VM without tini as PID 1.
- `api` and `cron` share the `cheetah-scans` volume; cron writes scan JSON, api reads.
- `oauth2-proxy` runs under the `oauth` profile — only starts with `docker compose --profile oauth up -d`.
- `OAUTH2_PROXY_EMAIL_DOMAINS` is set to `""` (not `"*"`). With `"*"` the email file becomes a no-op (OR semantics).

### Public exposure

Tailscale Funnel publishes the Mac book pro M5 (this machine)'s port 5173 at `https://ajays-macbook-pro.tailb3dc79.ts.net`. Friends don't need Tailscale installed — only the URL and a Google account in the allowlist.

---

## 3. Auth flow (Google OAuth + email allowlist)

```
Browser                nginx              oauth2-proxy        Google
   │                     │                     │                │
   │  GET /sepa          │                     │                │
   ├────────────────────▶│                     │                │
   │                     │  auth_request       │                │
   │                     ├────────────────────▶│                │
   │                     │   401 (no cookie)   │                │
   │                     │◀────────────────────│                │
   │  302 → /oauth2/sign_in?rd=...             │                │
   │◀────────────────────│                     │                │
   │  GET /oauth2/sign_in                      │                │
   ├──────────────────────────────────────────▶│                │
   │                     │   302 → Google      │                │
   │◀──────────────────────────────────────────│                │
   │  Google login + consent ─────────────────────────────────▶│
   │◀── code ────────────────────────────────────────────────── │
   │  /oauth2/callback?code=...                │                │
   ├──────────────────────────────────────────▶│                │
   │                     │  exchanges code, checks email file   │
   │                     │   ✅ in allowlist → set cookie       │
   │                     │   ❌ not in list   → 403             │
   │  302 → /sepa (cookie set)                 │                │
   │◀──────────────────────────────────────────│                │
   │  GET /sepa  (cookie)│                     │                │
   ├────────────────────▶│  auth_request 200   │                │
   │   ← SPA HTML        │                     │                │
```

After login, every `/api/*` call carries:
- `X-User-Email` (the authenticated email)
- `X-Access-Token` (Google access token; backend uses this once on first `/auth/me` to fetch name/picture)

Backend code reads `X-User-Email` from `request.headers` to scope todos / watchlist / price_alerts to the right person. (See `backend/auth.py`.)

**Email allowlist hot-reload:** `oauth2-proxy` watches `/etc/oauth2/emails.txt` and reloads on WRITE events. Editing `backend/oauth2-emails.txt` works without container restart, though restart is harmless and faster to verify.

---

## 4. Frontend (React 18 + Vite + TypeScript)

### Route map (`frontend/src/App.tsx`)

| Path | Page | Purpose |
|---|---|---|
| `/` → `/morning` | redirect | Default landing |
| `/morning` | MorningBrief | Pre-market brief: SEPA picks, Options Pulse summary, todos digest |
| `/overnight` | OvernightPage | 8pm–4am Blue Ocean ATS movers, Options Pulse summary embed |
| `/sepa` | SepaPage | **The main screen** — SEPA candidate list, hero, filters, breakout banner |
| `/sepa/:symbol` | SepaCandidatePage | Per-ticker detail: trade plan, chart, fundamentals, catalyst, insider |
| `/options` | OptionsPulsePage | SOIR-based bullish/bearish board across Russell 1000 |
| `/options/methodology` | OptionsPulseMethodology | Schaeffer formula write-up |
| `/catalysts` | CatalystsPage | Volume spikes, halts, frenzy radar, premarket sweep |
| `/watchlist` | WatchlistPage | User-added tickers with research enrichment |
| `/notifications` | NotificationsPage | Web Push subscription management |
| `/todos` | TodosPage | Todo list with reminder push notifications |
| `/lifeboard` | LifeboardPage | Mac Studio deal scraper |
| `/supply-demand` | SupplyDemandPage | Sector dependency graph |
| `/day-trading` | DayTrading | Intraday strategies + paper trades |
| `/dual-momentum` | DualMomentumPage | Antonacci-style momentum |
| `/chatter` `/chatter-india` | Chatter pages | Reddit/StockTwits sentiment |
| `/pioneers` | Pioneers | Curated thematic baskets |
| `/live` | LiveStream | Finnhub WebSocket SSE feed |
| `/track` | Track | Position tracker |
| `/tiny` | Tiny | Tiny-stocks sub-screener |
| `/glossary` | Glossary | Term definitions |

### State / data layer pattern

All pages fetch via custom hooks under `frontend/src/hooks/`. Two patterns dominate:

1. **Per-component hook + 30s polling** (e.g. `useBreakouts`, `useCatalysts`) — simple but each mount fetches once.
2. **Module-level shared store via `useSyncExternalStore`** (e.g. `useWatchlist` — single `_wlRows` cache with 5s TTL, listeners set, `notify()` fan-out). This is what stops 50 `<TickerLink>` components from each firing a fetch.

### SWR pattern (stale-while-revalidate)

`frontend/src/lib/swrCache.ts` wraps `localStorage` with versioned envelopes. `useSepaScan()` and `useSepaCandidate()` hydrate from cache instantly on mount, then revalidate in the background. Without this, every navigation back to `/sepa` showed a blank page for 5–30s.

- `MAX_BYTES = 8 MB` (full SEPA scans are ~3.4 MB)
- Slim fallback (`_slim<T>`) strips `all_results` field if too big

### Per-feature client state

| Concern | Where it lives |
|---|---|
| Dismissed breakout alerts | `localStorage: pounce.breakouts.dismissed_v1` (max 500 entries, FIFO trim) |
| Options Pulse filter chip | `localStorage: options_pulse_filter_v1` |
| Push subscription | `frontend/src/lib/pushSubscribe.ts` + service worker `frontend/public/sw.js` |
| Theme | `localStorage` via `useTheme` |

---

## 5. Backend (FastAPI on Python)

### Module map (`backend/`)

```
backend/
├── main.py                 ~93 KB — top-level FastAPI app, mounts sub-routers
├── auth.py                 X-User-Email parsing, get_current_user dep
├── cheetah_data.py         Hand-curated Cheetah Score universe (NVDA/META/PLTR…)
├── news.py                 Finnhub + Yahoo + Google News merge
├── crontab                 supercronic schedule (see §7)
├── oauth2-emails.txt       Email allowlist (hot-reloaded)
│
├── sepa/                   ◀── CORE: Minervini SEPA pipeline
│   ├── scanner.py          Orchestrator + composite score 0-100
│   ├── trend_template.py   8-criteria template
│   ├── stage.py            4-stage classifier
│   ├── rs_rank.py          IBD-style RS percentile
│   ├── vcp.py              VCP base detection (pivot quality, 325d lookback)
│   ├── power_play.py       +100%/8wk + ≤25% digest
│   ├── adr.py              ADR + liquidity gate
│   ├── canslim.py          C/A/I fundamentals (yfinance)
│   ├── catalyst.py         News + earnings + analyst revs
│   ├── insider.py          SEC EDGAR Form 4
│   ├── breakouts.py        High-vol breakout watcher (cron)
│   ├── vcp_watch.py        Hourly new-VCP detector (push notify)
│   ├── price_alerts.py     User price triggers
│   ├── alerts.py           Position-aware stop alerts
│   ├── notify.py           WhatsApp + Web Push fanout
│   ├── market_regime.py    SPY+QQQ trend gate
│   ├── prices.py           Massive + yfinance + parquet cache
│   ├── stock_analysis.py   Per-symbol deep-dive (chart + fundamentals)
│   ├── forum_chatter.py    Reddit/StockTwits velocity
│   ├── pioneers.py         Curated thematic baskets
│   └── cli.py              `python -m sepa.cli scan|fast-scan|brief|alerts|vcp-watch`
│
├── options/                ◀── Schaeffer's SOIR pulse
│   ├── soir.py             3-pillar classifier, Massive options chain (with lazy-disable on 401)
│   ├── scanner.py          Russell 1000 parallel scan (ThreadPoolExecutor, 20 workers)
│   └── api.py              Endpoints + history
│
├── analysis/
│   └── trade_plan.py       Wilder ATR(14), pivots, stops (base/2×ATR/7%), 1R/2R/3R targets
│
├── overnight/
│   ├── movers.py           Blue Ocean overnight gainers/losers (StockTwits scrape)
│   └── api.py
│
├── morning/
│   └── brief.py            Pre-market brief composer (pulls SEPA, options, todos, overnight)
│
├── catalysts/              Volume-spike / halts / frenzy / premarket / calendar
│   ├── api.py              All /catalysts/* endpoints
│   ├── volume_alerts.py    5-min cron: spike detection + WhatsApp/push
│   ├── premarket.py        Pre-market sweep
│   ├── halts.py            Trading halt feed
│   ├── frenzy.py           Frenzy radar
│   ├── calendar.py         Forward earnings/dividend calendar
│   ├── insiders.py         Per-ticker insider trades
│   ├── predictions.py      Tiny-stock predictions
│   └── history.py          Snapshot history
│
├── push/                   Web Push (VAPID)
│   ├── keys.py             VAPID keypair load/gen
│   ├── subs.py             Per-user subscription store
│   ├── sender.py           Deliver via pywebpush
│   └── hooks.py            Convenience helpers
│
├── watchlist/              User watchlist + research enrichment
├── learning/               Signal-grading loop (was learning/calibration)
├── lifeboard/              Mac Studio deal scraper
├── supply_demand/          Sector dependency graph + thesis
├── daytrading/             Intraday strategies + paper trades
├── todos/                  Todo list + reminder dispatcher
├── tiny_stocks/            Tiny-cap sub-screener
├── companies/              Company headline/about lookups
├── users/                  Per-user collection isolation
└── llm/                    LLM helpers (gemma_review etc.)
```

### API surface (top-level — abridged)

Full list lives in `backend/main.py` and the sub-router files. Major groupings:

**SEPA (`/sepa/*`)** — `scan`, `scan/stream` (SSE), `brief`, `candidate/{symbol}`, `rescan/{symbol}`, `analyze/{symbol}`, `dual-momentum`, `chatter/*`, `pioneers`, `india-universe`, `watchlist` (legacy), `position-plan`, `alerts/price`, `alerts/recent`, `breakouts`, `breakouts/scan`, `breakouts/{id}/dismiss`, `history/runs`, `history/diff`, `history/date/{et}`, `history/{symbol}`, `research/status`, `research/refresh`, `notify/test`, `smartmoney/{symbol}`.

**Options Pulse (`/options/soir/*`)** — `soir` (current scan), `soir/{symbol}`, `soir/refresh`, `soir/reclassify`, `soir/history/runs`, `soir/history/date/{iso}`, `soir/history/{symbol}`.

**Watchlist (`/watchlist/*`)** — current user-scoped watchlist. `GET /watchlist`, `POST /watchlist`, `DELETE /watchlist/{ticker}`, `POST /watchlist/{ticker}/refresh`.

**Quotes** — `GET /quote/{ticker}` (single, with overnight scrape fallback), `POST /quotes` (bulk).

**Catalysts (`/catalysts/*`)** — `scan`, `timeline`, `stale`, `frenzy-radar`, `halts`, `predictions`, `multi-day-accumulators`, `premarket`, `insiders/{ticker}`, `calendar`, `alerts/history`, `alerts/run`, `{ticker}`.

**Morning / Overnight** — `GET /morning/brief?force=bool`, `GET /overnight/movers`, `GET /overnight/symbol/{symbol}`.

**Live stream** — `GET /stream` (SSE — Finnhub trade feed via internal WebSocket consumer).

**Push (`/push/*`)** — `public-key`, `subscribe`, `unsubscribe`, `prefs`, `subscriptions`, `test`.

**Auth** — `GET /auth/me` (returns email, name, picture from cached Google userinfo).

**Todos** — `GET /todos`, `GET /todos/brief-slice`, `POST /todos`, `DELETE /todos/{id}`, `POST /todos/reminder/run`.

**Learning loop** — `headline`, `scoreboard`, `history`, `recent`, `top_winners`, `market_history`, `insights`, `ticker/{ticker}`, `backfill`, `resolve`, `calibrate`.

**Day trading (`/day/*`)**, **Supply/Demand (`/supply-demand/*`)**, **Lifeboard (`/lifeboard/*`)**, **Tiny stocks (`/tiny/*`)** — see sub-router files.

---

## 6. Data providers

| Provider | Subscription | Used for | Where called |
|---|---|---|---|
| **Massive Developer** ($79/mo) | Real-time stocks (was Polygon.io — same vendor) | SEPA daily bars + intraday quotes | `sepa/prices.py`, `main.py /quote` `/quotes` |
| **Finnhub** (free) | Live ticks + non-SEPA news + free company news | `/stream` SSE, `/news`, fallback quotes | `main.py`, `news.py` |
| **yfinance** (free, scraped) | CANSLIM fundamentals, fallback price history, options chains (since Massive plan tier doesn't include options) | `sepa/canslim.py`, `options/soir.py` fallback | various |
| **SEC EDGAR** (free) | Form 4 / 13D / 13G insider filings | `sepa/insider.py`, `catalysts/insiders.py` |
| **StockTwits scrape** | Live Blue Ocean ATS overnight prices (8pm–4am ET, not in any standard plan) | Overnight quotes for `/quote` and `/quotes` | `main.py _stocktwits_scrape_quote/_many` |
| **Yahoo / Google RSS** (free) | News merge | `news.py` |
| **Reddit/StockTwits** (scraped) | Forum chatter velocity | `sepa/forum_chatter.py`, `sepa/reddit_scrape.py` |

**Massive options gotcha:** the $79 plan tier returns 401 on `/v3/snapshot/options/{ticker}`. SOIR scanner sets a `_massive_options_disabled` global on first 401 and lazy-falls back to yfinance for the remainder of the run, avoiding 1000 wasted API calls.

**Phase routing:** `_market_phase_et()` returns `'overnight'` (8pm–4am), `'regular'` (9:30am–4pm), or `'closed'`. The single `/quote/{ticker}` endpoint routes:
- Overnight → StockTwits scrape (regex-extracts `extended_hours` block) → batch fallback → yfinance
- Regular → Massive → yfinance fallback
- Closed → yfinance

Bulk `/quotes` uses `asyncio.Semaphore(10)` for concurrent overnight scrapes, capped at 50 tickers.

---

## 7. Cron schedule (`backend/crontab`)

All times America/New_York. Run by supercronic in the `cron` container.

| Cron | Job | What |
|---|---|---|
| `0 20 * * 0` | `sepa.cli research-refresh` | Sun 8pm — heavy weekly research pre-warm |
| `30 16 * * 1-5` | `sepa.cli fast-scan` | Mon–Fri 4:30pm — post-close fast scan |
| `30 8 * * 1-5` | `sepa.cli brief` | Mon–Fri 8:30am — morning brief generation |
| `30 17 * * 1-5` | `options.scanner russell1000` | Mon–Fri 5:30pm — daily SOIR snapshot |
| `0 21 * * 0` | `options.scanner russell1000` | Sun 9pm — full SOIR sweep |
| `*/5 9-15 * * 1-5` + edge mins of 16 | `sepa.cli alerts` | Every 5min market hours — position alerts |
| `0 9-16 * * 1-5` | `sepa.cli vcp-watch` | Hourly market hours — new VCP push |
| `*/5 * * * *` | `lifeboard.macstudio scan` | Every 5min — Mac Studio deal scraper (self-rate-limits) |
| `0 6 * * *` | `supply_demand.tracker --force` | Daily 6am — sector graph refresh |
| `*/5 9-15 * * 1-5` + 16-edge | `catalysts.volume_alerts` | Every 5min — volume spike push |
| `0 4,6,8 * * 1-5` + `25 9 * * 1-5` | `catalysts.premarket.scan_premarket` | Pre-market sweeps |
| `0 5 * * *` | `catalysts.calendar.get_calendar(force=True)` | Daily 5am — forward calendar |
| `30 9-16 * * 1-5` | `catalysts._full_scan + history.record_snapshot` | Hourly market hours — catalyst snapshots |
| `15 * * * *` | `learning.resolver.resolve_pending` | Hourly — grade observations whose horizon expired |
| `0 17 * * 1-5` | `learning.calibrator.aggregate(snapshot=True)` | Mon–Fri 5pm — calibration row |
| `*/15 9-15 * * 1-5` + 16-edge | `sepa.breakouts.detect_all` | Every 15min — fresh breakout detection |
| `* * * * *` | `todos.reminder.fire_due` | Every minute — todo reminder dispatcher |
| `0 7 * * *` | `todos.reminder.fire_daily_digest` | Daily 7am — todo digest push |

**Cron container freshness gotcha:** `cron` and `api` share the same image but `up -d` doesn't always recreate `cron` if only its image is rebuilt. Always include `--force-recreate` after a backend code change so cron picks up the new code.

---

## 8. Persistence (MongoDB collections)

Database: `cheetah` (env `MONGO_DB`). Mongo bound to `127.0.0.1:27017` only — never exposed to LAN.

| Collection | Purpose |
|---|---|
| `scan_runs` | One row per SEPA scan with timestamp, mode, candidate count |
| `candidate_snapshots` | All candidates from each scan (joined into history endpoints) |
| `soir_history` | One row per SOIR scan run |
| `soir_latest` | Current SOIR snapshot keyed by symbol |
| `sepa_research_cache` | Pre-warmed CANSLIM/VCP/etc. so fast-scan only does price-derived work |
| `breakout_alerts` | Volume breakout + rising-momentum alerts (`/sepa/breakouts`) |
| `price_alerts` | User price triggers, scoped by `email` |
| `watchlist` | User-scoped watchlist with research enrichment |
| `todos` | User todos with `notify_at` for reminder dispatcher |
| `users` | Per-user profile (name, picture from Google userinfo) |
| `push_subscriptions` | Web Push endpoints + VAPID keys |
| `catalyst_snapshots` | Hourly volume/halt/frenzy snapshots |
| `catalyst_alerts_history` | Volume-spike alert log |
| `signal_calibration_history` | Daily calibration rows for the learning loop |
| `lifeboard_*` | Mac Studio deals + config |
| `supply_demand_*` | Sector graph + thesis |
| `learning_observations` | Pending observations awaiting horizon resolution |

Shared file volume `cheetah-scans` holds `~/.cheetah/scans/latest.json` so api can read what cron just wrote without a Mongo round-trip.

---

## 9. Major flows

### 9a. SEPA scan — the headline flow

```
┌──────────────┐    POST /sepa/scan        ┌────────────┐
│  /sepa page  │──────────────────────────▶│ FastAPI    │
└──────┬───────┘  (or SSE /sepa/scan/      │ main.py    │
       │           stream for progress)    └─────┬──────┘
       │                                         │
       │ ◀── SWR cache hit ── instant render ────│
       │                                         ▼
       │                                  sepa/scanner.py
       │                                         │
       │           ┌───────────────────┬─────────┼─────────┬───────────────┐
       │           ▼                   ▼         ▼         ▼               ▼
       │     Massive bars      Trend Template  RS rank  VCP / Power  CANSLIM (top 20)
       │     (per ticker)      (8 rules)       (IBD)    Play (book)   yfinance fundamentals
       │           │                   │         │         │               │
       │           └───────────────────┴────────┬┴─────────┴───────────────┘
       │                                        ▼
       │                              composite score 0–100
       │                              + rating: STRONG_BUY/BUY/WATCH/NEUTRAL/AVOID
       │                              + trade_plan (analysis/trade_plan.py)
       │                              + market regime gate (SPY+QQQ)
       │                                        │
       │                                        ▼
       │                            scan_runs + candidate_snapshots ┐
       │                                                            ▼
       │                                                         MongoDB
       │ ◀──── candidates JSON (~3.4 MB)                            │
       │                                                            │
       └──── localStorage SWR cache write ──────────────────────────┘
```

**On detail page** `/sepa/:symbol`: `useSepaCandidate(symbol)` hits `GET /sepa/candidate/{symbol}` and renders `<TradePlanPanel>` from `data.base.trade_plan`. The card shows the live `useQuote` overlay on top of `last_close`, with a 🌙 badge during overnight Blue Ocean prints.

### 9b. Options Pulse (Schaeffer's SOIR)

```
17:30 ET cron ──▶ options.scanner russell1000
                  │
                  ├── ThreadPoolExecutor(20 workers, per-thread requests.Session)
                  │
                  ▼
            For each of ~1000 tickers:
              1. Fetch options chain
                 Massive snapshot ──❌ 401── set _massive_options_disabled
                                          ↓
                                       yfinance fallback
              2. Compute SOIR (put OI / call OI ratio)
              3. 3-pillar classifier:
                 - SOIR percentile (vs ticker history)
                 - Trend pillar (record.stage.stage; 2=up, 4=down)
                 - SEPA score (from sepa_research_cache)
              4. → BULLISH / BEARISH / WATCH / NEUTRAL
              5. Attach trade_plan from sepa record if present
                  │
                  ▼
            soir_history (run row) + soir_latest (per-symbol)

Frontend /options page:
  ├── useSoirRuns()  → list dates for scrubber
  ├── useSoirScanByDate(date) → board for that date
  └── filter chip persisted to localStorage[options_pulse_filter_v1]
```

Also embedded: `<OptionsPulseSummary topN={5}>` on Overnight + Morning Brief shows a slim version inline.

### 9c. Morning Brief (8:30am ET)

```
08:30 ET cron ──▶ sepa.cli brief
                  │
                  ▼
            morning/brief.py composes:
              ├── SEPA top picks (from latest scan_runs)
              ├── Options Pulse summary (top 5 bullish + 5 bearish)
              ├── Overnight movers (from /overnight/movers cache)
              ├── Today's earnings (from catalysts/calendar)
              ├── Active price alerts firing today
              └── Todos brief-slice (important + due today)
                  │
                  ▼
              Cached in Mongo (or returned fresh with ?force=true)

Frontend useMorningBrief:
  - Auto-`?force=true` on first mount during 6–10am ET window
  - Otherwise serves cached
```

### 9d. Overnight (Blue Ocean ATS)

The hard problem: standard data plans don't see Blue Ocean's 8pm–4am session. StockTwits's symbol pages do (their feed has a `session_type: OVERNIGHT_PRE_MARKET` JSON block).

```
Frontend useQuote(ticker)
          │
          ▼
GET /quote/AMD
          │
   ┌──────┴──────┐
   ▼ overnight   ▼ regular/closed
   │             │
   asyncio.to_thread(_stocktwits_scrape_quote)
   │
   ├── fetch https://stocktwits.com/symbol/AMD (~250 KB)
   ├── regex extract "extended_hours":{"price":418.6,...,"session_type":"OVERNIGHT_PRE_MARKET"}
   │
   ▼ if no extended_hours block (regular hours, expected to return None)
   _stocktwits_quote (batch)  ──▶ ql.stocktwits.com/batch (gives 8pm post-close only)
   │
   ▼ fallback
   yfinance quote
          │
          ▼
   { last_price, day_pct, _source, _extended, _ext_type, ... }
          │
          ▼
   60s client memo + 60s backend cache
```

`<SepaCandidateCard>` shows a 🌙 overnight badge when `liveQuote._extended` is true.

Bulk `/quotes` for the whole SEPA list: `asyncio.Semaphore(10)` cap, max 50 tickers per request, batch fallback for the remainder.

### 9e. Breakout alerts (the dismiss flow)

```
*/15 9-15 cron ──▶ sepa.breakouts.detect_all ──▶ breakout_alerts collection

Frontend useBreakouts (30s polling):
  - GET /sepa/breakouts?since=0&limit=50
  - filter by dismissedRef.current (localStorage:pounce.breakouts.dismissed_v1)
  - render <BreakoutAlertBanner> stack

User clicks X on alert:
  1. Optimistic UI:        setAlerts(rows.filter(r => r._id !== id))
  2. Local persist:        dismissedRef.add(id) + _saveDismissed
  3. Backend best-effort:  POST /sepa/breakouts/{id}/dismiss
  ↑
  Without (2), the 30s refetch would re-show the alert because backend cron
  may have created a fresh duplicate alert for the same underlying signal.
  Local set survives refetch + reload + browser restart, capped at 500.
```

### 9f. Catalysts (volume spikes)

Two-tier thresholds:
- **Scan tier** (page display) — moderate thresholds
- **Push tier** (notifications) — strict: $10M dvol, 10× surge, $1+ price, $50M+ cap

```
*/5 9-15 cron ──▶ catalysts.volume_alerts
                  ├── scan with PUSH-tier thresholds
                  ├── for each fresh ticker: deliver Web Push + log to catalyst_alerts_history
                  └── fires AT MOST ONCE per ticker per session

Page hits /catalysts/scan:
  - SCAN-tier thresholds (more permissive)
  - never causes pushes
  - records hourly snapshot to catalyst_snapshots
```

### 9g. Watchlist (shared module-level cache)

```
50 <TickerLink> render simultaneously
       │  each calls useWatchlistSet()
       ▼
useSyncExternalStore(subscribe, snapshot, snapshot)
       │
       ▼  module-level _wlRows[] + 5s TTL
fetchOnce()  ── debounced; only one network call total
       ▼
GET /watchlist
       │
       ▼
notify() fan-out to all 50 listeners
```

Auto-poll every 4s while any entry has `status: 'queued' | 'researching'` (background research enrichment runs server-side).

### 9h. Web Push (no Twilio, no SaaS)

```
Frontend Notifications page
    │
    │ Notification.requestPermission()
    ▼
ServiceWorker registers /sw.js
    │
    │ navigator.serviceWorker.ready.pushManager.subscribe({
    │   userVisibleOnly: true,
    │   applicationServerKey: <VAPID pub key from /push/public-key>
    │ })
    ▼
POST /push/subscribe { endpoint, keys, email } → push_subscriptions collection

Backend send path (any cron job that wants to notify):
    push.sender.send(email, payload)
        │
        ▼
    pywebpush.webpush(subscription, json.dumps(payload), vapid_private_key, vapid_claims)
        │
        ▼
    Browser shows native OS notification, even with the tab closed

Foreground-tab fallback:
    Frontend polls /catalysts/alerts/history etc. and pops a Notification API
    on its own when it sees new entries — covers Chrome-foreground-tab edge case.
```

**Auto-subscribe on permission grant:** `<NotificationsPage>` checks if `Notification.permission === 'granted'` but `subscriptions[email].endpoint == null` and re-subscribes silently (handles the case where a user granted permission once but lost the subscription — common after browser data clear).

### 9i. Authentication path on every request

```
Cookie present?
  ├── No  → 302 /oauth2/sign_in
  └── Yes → oauth2-proxy validates → sets X-Auth-Request-Email response header
            │
            ▼
        nginx reads X-Auth-Request-Email, sets X-User-Email on upstream
            │
            ▼
        FastAPI Depends(get_current_user) reads X-User-Email
            │
            ├── First time?  Use X-Access-Token to fetch /oauth2/v3/userinfo
            │                Persist {email, name, picture} to users collection
            └── Subsequent?  Just return email-scoped queries
```

---

## 10. Caching layers (cheat sheet)

| Layer | What | TTL |
|---|---|---|
| Browser localStorage SWR | SEPA scan, candidate detail, dismissed alerts, filter prefs | until cleared |
| `useSyncExternalStore` module store | Watchlist (one fetch across 50 components) | 5 s |
| `_quoteMemo` Map | Per-symbol live quote | 60 s (matches backend) |
| FastAPI in-memory dict | News per symbol | 3 min |
| FastAPI in-memory dict | Quote (regular hours via Massive) | 60 s |
| FastAPI in-memory dict | Overnight movers | 120 s premarket / 600 s regular / 1800 s else |
| FastAPI in-memory dict | Catalyst calendar | 6 h (cron forces daily) |
| Mongo `sepa_research_cache` | CANSLIM / VCP / liquidity / ADR / IPO age | overwritten by Sun research-refresh |
| Parquet on `cheetah-scans` volume | Daily price bars per ticker | overwritten by next scan |

---

## 11. Configuration (`backend/.env`)

| Var | Required | Purpose |
|---|---|---|
| `MASSIVE_API_KEY` | Yes (for SEPA) | Real-time daily bars + intraday quotes |
| `FINNHUB_API_KEY` | Yes (for live stream + free news) | WebSocket trades + REST news |
| `MONGO_URL` | Yes | `mongodb://mongo:27017` in compose |
| `MONGO_DB` | No | Defaults to `cheetah` |
| `TZ` | No | `America/New_York` (set in compose) |
| `OAUTH2_PROXY_CLIENT_ID` / `_CLIENT_SECRET` / `_COOKIE_SECRET` / `_REDIRECT_URL` | Yes (for oauth profile) | Google OAuth |
| `SOIR_UNIVERSE_MODE` | No | Defaults to `russell1000` for SOIR scanner |
| `SEPA_UNIVERSE_MODE` | No | Defaults to `russell1000` for SEPA |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` | Yes (for Web Push) | Auto-generated on first run if missing |

---

## 12. Update / redeploy procedures

| What changed | Command |
|---|---|
| Email allowlist only | `docker compose restart oauth2-proxy` (or just edit — file is hot-reloaded) |
| Backend code | `docker compose build api && docker compose up -d --force-recreate api cron` (cron must recreate to pick up new image) |
| Frontend code | `docker compose build frontend && docker compose up -d --force-recreate frontend` |
| Everything | `git pull && docker compose build && docker compose up -d --force-recreate` |
| Add a new env var | Edit `backend/.env` → restart `api` and `cron` |

---

## 13. Known limits / gotchas

- **Massive plan tier doesn't include options.** `_massive_options_disabled` lazy-disables on first 401 to avoid wasting calls. Upgrading to Polygon Options Developer (~$79/mo) would replace the yfinance options fallback.
- **StockTwits scrape is HTML-regex extraction.** A page redesign breaks it. The `extended_hours` JSON block is currently embedded server-side in their symbol pages.
- **No rate-limiting** on the API. Behind oauth2-proxy + email allowlist this is acceptable; it would not be if exposed publicly without auth.
- **Cron container pinned to image at create time.** Always `--force-recreate` after backend rebuilds. There is no auto-update on `:latest` digest changes.
- **Tailscale Funnel exposes the Mac book pro M5 (this machine) publicly.** oauth2-proxy is the only gate. Email allowlist must stay tight.
- **No tests.** Snapshot test of `_analyze_symbol` on a known-good ticker is the highest-leverage missing thing.
- **9 Minervini thresholds in `sell_signals.py` and `ipo_age.py` are unverified against the book.** Listed in `HANDOFF.md`.
- **`api.polygon.io` and `api.massive.com` are the same vendor** (rebrand Oct 2025). Don't treat Massive as a Polygon alternative.

---

## 14. Quick reference — where to look when something breaks

| Symptom | First place to look |
|---|---|
| Login redirect loop | oauth2-proxy logs; `OAUTH2_PROXY_REDIRECT_URL` matches Tailscale URL? |
| Email not allowed | `backend/oauth2-emails.txt` — and `OAUTH2_PROXY_EMAIL_DOMAINS` is `""` not `"*"` |
| Scan times out | `cheetah-scans` volume; Massive API key still valid; `docker compose logs api` |
| Cron not firing | `docker compose logs cron`; container TZ is `America/New_York`?; `init: true`? |
| Cron fires old code | `--force-recreate` after `build` |
| Empty `/sepa` after navigation back | `swrCache.ts` MAX_BYTES too small (should be 8 MB) |
| Alerts re-appear after dismiss | `localStorage: pounce.breakouts.dismissed_v1` cleared? |
| Overnight quotes stale | StockTwits scrape — only active 8pm–4am ET; regex match check `_stocktwits_scrape_quote` |
| Push notifications silent | `/push/subscriptions` empty for that email; permission still granted? |
| All SOIR rows NEUTRAL | `_trend_pillar` should read `record.stage.stage` (not `record.sma_*`) |
| 502 from api | Python syntax error in main.py — `docker compose logs api --tail 100` |
| Frontend can't reach api | nginx `proxy_pass http://api:8000/` — both on compose network? |

---

## 15. Source-of-truth files

When this document and code disagree, code wins. The least-fragile pointers:

- Compose: `docker-compose.yml`
- nginx: `frontend/nginx.conf`
- Cron: `backend/crontab`
- Routes (frontend): `frontend/src/App.tsx`
- Routes (backend): `backend/main.py` + `backend/*/api.py`
- SEPA pipeline: `backend/sepa/scanner.py`
- SOIR pipeline: `backend/options/soir.py` + `backend/options/scanner.py`
- Trade plan: `backend/analysis/trade_plan.py`
- Push system: `backend/push/` + `frontend/public/sw.js` + `frontend/src/lib/pushSubscribe.ts`
- Auth glue: `backend/auth.py` + `frontend/nginx.conf` (auth_request blocks)
