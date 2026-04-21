# Cheetah Market App

A single-page app for short-term "cheetah-style" stock screening plus a live market stream.

## Two routes, one repo, one backend

**`/dashboard`** — research layer:

- Cheetah Score formula + 12 indicators + 8 industry-expert frameworks (O'Neil, Greenblatt, Piotroski, Lynch, Minervini, Buffett, Graham, Weinstein).
- **Rerun formulas** button — backend recomputes scores live from `FORMULA_WEIGHTS × bucket_scores` on every request.
- **Tier 1 Cheetahs** — 18 stocks with Tier 2 / Tier 3 competitor map, color-coded key signals, and "why it's running" rationale.
- **Competitor Scout** — NVDA's and CRDO's growing direct competitors side-by-side (NVDA: AMD, AVGO, MRVL, ARM, TSM, MU · CRDO: ALAB, MRVL, AVGO, COHR, LITE, SMTC, MTSI). Each peer has overlap area, growth, GM, PEG, RS, 3M, status, and a read-note.
- **Private unicorns** — 12 rapidly-growing private companies (OpenAI, Anthropic, xAI, Databricks, SpaceX, Stripe, Cerebras, Groq, Figure, Anduril, Perplexity, Scale) with indirect public-market proxies.
- **Thematic ETFs** — 12 basket-exposure options (SMH, SOXX, QQQM, IGV, BOTZ, WCLD, IBIT, ARKW, ITA, URNM, XBI, TAN).
- **Real-time news** — aggregated from Finnhub company news + Yahoo Finance RSS + Google News RSS, cached 3 minutes, auto-refreshes. Tabs for Market / NVDA / CRDO / PLTR / META / LLY / ALAB / AVGO / MRVL.

**`/live`** — real-time quotes via Server-Sent Events. Server-side RSI(14) and VWAP, canvas sparklines, and the cheetah score joined back in per ticker.

## Project layout

```
cheetah-market-app/
├── backend/
│   ├── main.py              # FastAPI: /stream /cheetah /competitors /unicorns /etfs /news /snapshot /health
│   ├── cheetah_data.py      # Stocks + unicorns + ETFs + competitor groups; compute_score()
│   ├── news.py              # Finnhub + Yahoo RSS + Google News scraper with cache
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── package.json
    ├── vite.config.ts       # Proxies all backend routes to :8000
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── main.tsx         # BrowserRouter
        ├── App.tsx          # Routes
        ├── styles.css       # Dark theme
        ├── types.ts
        ├── components/
        │   ├── NavBar.tsx
        │   ├── FormulaCard.tsx
        │   ├── IndicatorsCard.tsx
        │   ├── CheetahTable.tsx
        │   ├── CompetitorScoutCard.tsx   # NVDA + CRDO growing rivals
        │   ├── UnicornsCard.tsx          # Private unicorns
        │   ├── EtfsCard.tsx              # Thematic ETFs
        │   ├── NewsPanel.tsx             # Aggregated real-time news
        │   ├── RefreshButton.tsx         # Rerun formulas
        │   ├── QuoteRow.tsx
        │   └── Sparkline.tsx
        ├── hooks/
        │   ├── useCheetahStocks.ts       # Exposes refetch()
        │   ├── useMarketStream.ts
        │   └── useJsonApi.ts             # Generic GET helper
        └── pages/
            ├── Dashboard.tsx
            └── LiveStream.tsx
```

## The Cheetah Score

```
Score = 0.30·Growth + 0.20·Momentum + 0.20·Quality + 0.15·Stability + 0.15·Value
```

Each stock carries 0-100 scores for the five buckets in `backend/cheetah_data.py`. The backend applies `FORMULA_WEIGHTS` freshly on every `/cheetah` request, so:

- Edit weights or a bucket → click **Rerun formulas** on the dashboard → the list re-sorts live.
- No rebuild needed. No client-side math.

## Growing-competitor scouting

Two anchored groups are maintained in `COMPETITOR_GROUPS` inside `cheetah_data.py`:

| Anchor | Growing direct competitors |
| --- | --- |
| **NVDA** | AMD (MI300), AVGO (custom ASIC), MRVL (Trainium ASIC + optical DSP), ARM (Neoverse IP), TSM (CoWoS enabler), MU (HBM3E) |
| **CRDO** | ALAB (PCIe retimers), MRVL (optical DSP), AVGO (PAM4 DSP + switches), COHR (transceivers), LITE (800G optical), SMTC (CopperEdge AEC), MTSI (analog RF) |

Each peer row carries product overlap, Rev YoY, GM, PEG, RS, 3M, a `growing/challenger/enabler` status pill, and a one-line read-note.

## Real-time news scraping

`backend/news.py` hits three free sources in parallel and merges the results:

1. **Finnhub `/company-news`** — needs the API key you already have; rich metadata and publisher tagging.
2. **Yahoo Finance RSS** — `feeds.finance.yahoo.com/rss/2.0/headline?s=...`, no key.
3. **Google News RSS** — `news.google.com/rss/search?q=...+stock`, no key.

Titles are normalized and deduplicated (lowercase + alnum), sorted by publish time, capped at 12 items, and cached for 3 minutes per ticker.

Endpoint: `GET /news?symbol=NVDA` (or omit `symbol` for general market news).

## Run it

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# paste your free Finnhub key in .env
uvicorn main:app --reload --port 8000
```

Sanity: http://localhost:8000/health, http://localhost:8000/cheetah, http://localhost:8000/news?symbol=NVDA.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

http://localhost:5173 → lands on `/dashboard`.

Vite proxies `/stream`, `/cheetah`, `/competitors`, `/unicorns`, `/etfs`, `/news`, `/snapshot`, `/health` to `localhost:8000`.

## Disclaimer

Educational / research tool. Cheetah scores + bucket scores are heuristic composites from public data. Finnhub's free tier is real-time during US market hours and last-trade off-hours. News scraping uses publicly available RSS feeds and Finnhub's free news endpoint; respect each source's terms of use. Not financial advice. Do not use for automated execution without verifying tick-by-tick accuracy against a licensed market-data vendor.
