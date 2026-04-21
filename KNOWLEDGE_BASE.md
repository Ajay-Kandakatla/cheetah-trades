# Cheetah Market App — Knowledge Base

## Purpose
A dual-route SPA for short-term stock screening and live market tracking. Combines a proprietary "Cheetah Score" with real-time quotes, competitor intelligence, private unicorn proxies, thematic ETFs, and aggregated news. Designed for traders identifying high-growth momentum stocks.

---

## Tech Stack

### Backend
| Package | Version | Role |
|---------|---------|------|
| FastAPI | 0.115.4 | Async web framework + SSE streaming |
| Uvicorn | 0.32.0 | ASGI server |
| HTTPX | 0.27.2 | Async HTTP client (news scraping, Finnhub REST) |
| WebSockets | 13.1 | Finnhub real-time feed consumer |
| Python-dotenv | 1.0.1 | Environment variable management |

### Frontend
| Package | Version | Role |
|---------|---------|------|
| React | 18.3.1 | UI framework |
| React Router DOM | 6.27.0 | Client-side routing |
| Vite | 5.4.10 | Build tool + dev server |
| TypeScript | 5.6.3 | Type safety |

No CSS framework — custom dark theme CSS.

---

## Project Structure

```
cheetah-market-app/
├── backend/
│   ├── main.py           # FastAPI app, SSE streaming, WebSocket consumer
│   ├── cheetah_data.py   # All data + Cheetah Score computation engine
│   ├── news.py           # News aggregation (Finnhub + Yahoo + Google RSS)
│   └── requirements.txt
└── frontend/
    └── src/
        ├── types.ts          # All TypeScript interfaces
        ├── styles.css        # Dark theme (bg: #0b0d12, text: #e6e8ef)
        ├── hooks/
        │   ├── useJsonApi.ts       # Generic GET hook (no caching)
        │   ├── useCheetahStocks.ts # Fetches /cheetah, exposes refetch()
        │   └── useMarketStream.ts  # EventSource to /stream, quote dict
        ├── pages/
        │   ├── Dashboard.tsx   # /dashboard — screener/research page
        │   └── LiveStream.tsx  # /live — real-time tick-by-tick page
        └── components/
            ├── NavBar.tsx
            ├── FormulaCard.tsx
            ├── IndicatorsCard.tsx
            ├── CheetahTable.tsx
            ├── RefreshButton.tsx
            ├── CompetitorScoutCard.tsx
            ├── UnicornsCard.tsx
            ├── EtfsCard.tsx
            ├── NewsPanel.tsx
            ├── QuoteRow.tsx
            └── Sparkline.tsx
```

---

## Pages

### `/dashboard` (Default)
Research-focused historical screener.

| Component | Description |
|-----------|-------------|
| `FormulaCard` | Displays 5-factor Cheetah Score formula |
| `IndicatorsCard` | 12 technical/fundamental indicators + 8 expert frameworks |
| `CheetahTable` | Sortable/filterable table of 18 Tier 1 stocks |
| `CompetitorScoutCard` | NVDA and CRDO peer comparison groups |
| `UnicornsCard` | 12 private unicorn companies with public proxies |
| `EtfsCard` | 12 thematic ETFs with returns |
| `NewsPanel` | Aggregated headlines (9 symbol tabs, auto-refresh 3min) |
| `RefreshButton` | Triggers live formula recompute via `/cheetah` |

### `/live`
Real-time tick-by-tick streaming dashboard.
- Dynamic watchlist (add/remove tickers)
- Per-symbol `QuoteRow` with price, RSI(14), VWAP, sparkline, flash on change
- Connection status indicator (yellow/green/red/gray dot)

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service status, cached symbols, finnhub config |
| `/snapshot` | GET | All cached quotes as JSON dict |
| `/cheetah` | GET | Cheetah Scores recomputed fresh on every call |
| `/competitors` | GET | Growing peer groups for NVDA and CRDO |
| `/unicorns` | GET | 12 private unicorn companies |
| `/etfs` | GET | 12 thematic ETFs |
| `/news` | GET | Aggregated headlines; optional `?symbol=NVDA` param |
| `/stream` | GET (SSE) | Real-time quotes via Server-Sent Events |

**Vite Dev Proxy:** All backend routes proxied from port 5173 → 8000.

---

## Cheetah Score Engine

**Formula:** `score = 0.30·Growth + 0.20·Momentum + 0.20·Quality + 0.15·Stability + 0.15·Value`

- Each factor scored 0–100 (hardcoded in `cheetah_data.py`)
- Weights applied dynamically on every `/cheetah` request
- Results sorted descending by score
- Rerun via dashboard "Refresh" button

**Expert Frameworks Referenced:**
O'Neil CAN SLIM, Greenblatt Magic Formula, Piotroski F-Score, Lynch PEG, Minervini SEPA, Buffett Moat, Graham Safety Margin, Weinstein Stage Analysis

---

## Real-Time Data Pipeline

```
Finnhub WebSocket (trades)
    → QuoteCache.update()
    → SSE generator (event: quote)
    → Frontend EventSource
    → quotes dict state
    → QuoteRow re-render

Finnhub REST poller (every 5s)
    → QuoteCache.update() (OHLV + % change)
    → SSE broadcast if timestamp newer
```

**Server-side computations:**
- **RSI(14):** Wilder's smoothing algorithm
- **VWAP:** Rolling volume-weighted average price
- **Sparkline:** Last 32 prices as canvas line chart

**Default subscribed symbols:** NVDA, META, AAPL, MSFT, TSLA, AMD, PLTR, CRDO, AVGO, LLY

---

## News Aggregation (`news.py`)

Three parallel sources per symbol:
1. **Finnhub** `/company-news` (7-day window, requires `FINNHUB_API_KEY` env var)
2. **Yahoo Finance RSS** (public, no key)
3. **Google News RSS** (public, no key)

- Merged, deduplicated by normalized title, sorted by publish time, capped at 12 items
- In-memory cache per symbol, **3-minute TTL**
- Frontend auto-refreshes every 3 minutes to match TTL

---

## Data Models (`types.ts`)

| Type | Key Fields |
|------|-----------|
| `Quote` | symbol, price, volume, change, OHLV, pctChange, rsi14, vwap, sparkline, source, ts |
| `CheetahStock` | ticker, name, sector, mcap, revGrowth, grossMargin, debtRev, peg, rs, perf3m, score, buckets, signals, tier2, tier3, why |
| `CheetahResponse` | weights, stocks[], computedAt |
| `CompetitorGroup` | anchor ticker, headline, peers[], anchorStock |
| `CompetitorPeer` | ticker, name, overlap, metrics, status (growing/challenger/enabler) |
| `Unicorn` | name, sector, valuation ($B), revGrowth, arr, founders, note, indirectPublic[] |
| `Etf` | ticker, name, theme, expenseRatio, topHoldings, ytd, oneYear, note |
| `NewsItem` | title, url, summary, source, published (unix), provider |

---

## 18 Cheetah Stocks

| Ticker | Sector |
|--------|--------|
| NVDA, AVGO | AI / Semis |
| PLTR | AI / Software |
| CRDO, ALAB | AI / Connectivity |
| CLS | AI Hardware |
| VRT | AI Infrastructure |
| LITE | AI Optics |
| META | Mega-cap Tech |
| LLY | Pharma (GLP-1) |
| ABNB | Consumer / Travel |
| NET | Cloud / Security |
| RKLB | Space / Defense |
| OKLO | Nuclear / Energy |
| SOFI | Fintech |
| HIMS | Telehealth |
| SRPT | Biotech (Gene Therapy) |
| HRMY | Biotech (Rare Neuro) |

---

## Competitor Scout Groups

- **NVDA peers:** AMD, AVGO, MRVL, ARM, TSM, MU (AI chip/memory/custom ASIC)
- **CRDO peers:** ALAB, MRVL, AVGO, COHR, LITE, SMTC, MTSI (AI data-center connectivity)

---

## Unicorns with Public Proxies (12)

OpenAI → MSFT/NVDA | Anthropic → AMZN/GOOGL | xAI → TSLA/NVDA | Databricks → SNOW/AMZN | SpaceX → RKLB/IRDM | Stripe → SQ/PYPL | Cerebras → NVDA/AMD | Groq → AMD | Figure → TSLA/ABB | Anduril → LMT/RTX | Perplexity → GOOGL/MSFT | Scale → NVDA/PLTR

---

## Caching Strategy

| Layer | Cache | TTL |
|-------|-------|-----|
| Frontend | None (`cache: 'no-store'`) | — |
| Backend news | In-memory dict per symbol | 3 min |
| Backend quotes | In-memory rolling window (64 ticks) | None |

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `FINNHUB_API_KEY` | Yes (for live data) | Finnhub WebSocket + REST + news |

---

## Running the App

```bash
# Backend
cd backend
pip install -r requirements.txt
FINNHUB_API_KEY=your_key uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev   # Starts on localhost:5173
```

---

## Disclaimer
Not financial advice. Heuristic composite from public data. Finnhub free tier is real-time during US market hours, last-trade off-hours. Do not use for automated execution without verifying tick accuracy against a licensed vendor.
