# Cheetah Market App

> A self-hosted equity research dashboard for swing traders. Minervini's SEPA screener,
> live tick stream, curated growth-stock board, and WhatsApp price alerts — running on
> your own machine, with your own API keys.

If you've ever wished TradingView, Finviz, and Mark Minervini's checklist lived in one
opinionated app you could fully control, this is that. One repo, one Docker compose,
four containers, your data.

## What's inside

**📊 SEPA Screen** (`/sepa`) — the headline feature.
A full Specific Entry Point Analysis pipeline in Python: Trend Template (8 rules) → RS rank
≥ 70 → Stage 2 classifier → VCP / Power-Play base detection → risk-managed entry with pivot
and stop. Market-regime aware (SPY + QQQ gate). Catalyst enrichment (news, earnings, analyst
revisions) and insider activity (SEC EDGAR Form 4) bolted on. Click any candidate for a
full-page detail view with TradingView chart, R-multiple ladder, position-size planner, and
"+ Add to watchlist" / 🔔 price-alert buttons.

**🔔 Price alerts** — per-symbol price triggers stored in Mongo. Cron checks every 5 min
during market hours and fires via WhatsApp (Twilio) and/or browser notifications. Position-
aware alerts also watch your watchlist for stop-loss breaches.

**📈 Live stream** (`/live`) — Server-Sent Events feed from Finnhub WebSocket, with
server-side RSI(14), VWAP, and canvas sparklines. Cheetah scores joined per ticker.

**🦌 Curated dashboard** (`/dashboard`) — hand-tuned universe of US growth stocks with a
5-factor Cheetah Score (growth/momentum/quality/stability/value), competitor scout for NVDA
and CRDO peers, private-unicorn proxies (OpenAI, Anthropic, xAI, …), thematic ETF baskets,
and a live news panel aggregating Finnhub + Yahoo RSS + Google News.

**🇮🇳 Indian market** — NSE/BSE quotes via yfinance + Indian-edition Google News.

## Stack

- **Backend** — FastAPI, httpx, websockets, yfinance, MongoDB (price cache + scan history),
  parquet fallback at `~/.cheetah/prices/`.
- **Frontend** — React 18 + Vite + TypeScript, react-router-dom 6, plain CSS.
- **Scheduler** — supercronic in a sidecar container (cron syntax, container-native logging).
- **Notifications** — Twilio WhatsApp + browser Notification API.
- **Deploy** — `docker compose up -d`. Four containers: `mongo`, `api`, `cron`, `frontend` (nginx).

## Quick start (Docker — recommended)

```bash
git clone https://github.com/Ajay-Kandakatla/cheetah-trades.git
cd cheetah-trades/cheetah-market-app
cp backend/.env.example backend/.env     # fill in keys (see below)
docker compose up -d --build
```

Open http://localhost — you'll land on `/dashboard`. SEPA is at `/sepa`. First scan takes
30s without catalyst, 2–4 min with catalyst on.

### Required keys in `backend/.env`

| Var | What for | Where to get it |
|---|---|---|
| `FINNHUB_API_KEY` | Live ticks + non-SEPA news | finnhub.io free tier |
| `MASSIVE_API_KEY` | SEPA price history (real-time, paid) | massivedeveloper.com ($79/mo tier) |
| `MONGO_URL` | Price cache + scan runs | defaults to compose `mongo:27017` |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM` / `TWILIO_TO` | WhatsApp alerts | Twilio sandbox is free |

Finnhub-only mode works for everything except SEPA — the SEPA pipeline needs more history
than the free Finnhub tier allows.

## Local dev (no Docker)

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000

# frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Frontend at http://localhost:5173, Vite proxies API calls to `:8000`.

## How to use it

**Run a SEPA scan.** Visit `/sepa`, hit **Scan**. With *Include catalyst* on (default) it
fetches news + earnings for each candidate — slower, but lights up the Catalyst and
Fundamentals tabs. Off, you get a structural-only scan in ~30s.

**Read the hero.** The market-regime card on the left is the gate: *Confirmed Uptrend* =
safe to long, *Mixed* = reduce size, *Caution* = stand aside. The "since last scan" stat
tells you how stale the data is.

**Drill into a candidate.** Click any card → full-page view at `/sepa/AAPL` with a 6-tab
breakdown (Chart / Setup / Trend / Fundamentals / Catalyst / Insider). Shareable URL,
back button works.

**Set a price alert.** Click 🔔 on any candidate. Pick *above* or *below* a level, choose
WhatsApp + browser. The cron container checks every 5 min during US market hours. Fires
log to `/sepa/alerts/recent`.

**Save a watchlist entry.** "+ Add to watchlist" stores symbol + entry + stop + share
count. The alerts cron also watches these for stop-loss breaches.

**Edit the curated dashboard.** Open `backend/cheetah_data.py`, tweak weights or bucket
scores, hit **Rerun formulas** on `/dashboard` — the list re-sorts live with no rebuild.

## Project layout

```
cheetah-market-app/
├── docker-compose.yml          # mongo + api + cron + frontend
├── SPECS.md                    # full technical spec (every endpoint, module, gotcha)
├── backend/
│   ├── main.py                 # FastAPI: /cheetah /sepa/* /stream /alerts/* …
│   ├── cheetah_data.py         # Curated universe + 5-factor score
│   ├── news.py                 # Finnhub + Yahoo + Google News merge
│   ├── sepa/                   # Trend template, RS rank, stage, VCP, base count,
│   │                           # sell signals, catalyst, insider, risk, scanner, alerts
│   ├── crontab                 # supercronic schedule
│   └── Dockerfile
└── frontend/
    └── src/
        ├── pages/              # Dashboard / LiveStream / Sepa / SepaCandidate
        ├── components/         # SepaHero, SepaCandidateCard, PriceAlertModal, …
        └── hooks/              # useSepa, usePriceAlerts, useMarketStream, …
```

See [SPECS.md](SPECS.md) for the full endpoint table, module breakdown, and deployment
notes (including the `init: true` gotcha for supercronic on Apple Silicon).

## Why you might want this

- You already pay for a price-data provider and want the screener built around your
  workflow instead of theirs.
- You want a real Minervini SEPA pipeline, not a checkbox UI on top of someone else's
  scanner.
- You're comfortable running a 4-container compose on a Mac mini / NUC / VPS.
- You want WhatsApp alerts that fire from your own cron, not a SaaS you can't introspect.

## Disclaimer

Educational / research tool. Cheetah scores, SEPA scoring, and bucket scores are heuristic
composites computed from public market data. Finnhub's free tier is real-time during US
market hours and last-trade off-hours; Massive Developer is real-time intraday for SEPA.
News scraping uses publicly available RSS feeds and Finnhub's free news endpoint — respect
each source's terms of use. Not financial advice. Do not wire this to automated execution
without verifying tick-by-tick accuracy against a licensed market-data vendor.
