# Cheetah Market App — Session Handoff

**Last updated:** 2026-04-25
**Repo:** `/Users/ajay/clinet-test/cheetah-market-app`
**Stack:** FastAPI + asyncio + yfinance + parquet · React 18 + Vite + TypeScript · launchd cron · macOS dev

---

## 1. Open task — what to do next session

The user's explicit next-session brief:

> **"Build the UI and focus on US stock market only."**

This means two things:

### 1a. Strip India-market features (pivot to US-only)

**Files to delete:**
- `frontend/src/pages/IndianMarket.tsx`
- `frontend/src/components/EnhancedIndianStockTable.tsx`
- `frontend/src/components/IndianMarketIndices.tsx`
- `frontend/src/components/IndianNewsPanel.tsx`
- `frontend/src/components/IndianStockTable.tsx`
- `frontend/src/hooks/useIndianStocks.ts`

**Files to edit:**
- `frontend/src/App.tsx` — remove `/india` route and `IndianMarket` import
- `frontend/src/components/NavBar.tsx` — remove the `India` `NavLink`
- `frontend/src/pages/ModernDashboard.tsx` — remove the "№ 03 — Regional / Indian market insights" section (lines ~127-139) and the `EnhancedIndianStockTable` import
- `frontend/src/pages/Dashboard.tsx` — dead-routed per spec audit; either delete or also strip India refs
- `frontend/src/types.ts` — drop India-only types

**Backend** — user blocked the `grep` that would have shown India endpoints. Run this first to see what's there:
```bash
grep -rn -iE "india|/nse|/bse" backend --include="*.py" | grep -v .venv
```
Likely candidates: any `india_*` route in `main.py`, any `india` module under `backend/`. Only remove what's clearly India-market — leave US-stock infra untouched.

**Verify after each deletion:**
```bash
cd frontend && npx tsc -b --noEmit
```

### 1b. Actually run/verify the new SEPA UI in a browser

The UI components exist and TypeScript compiles, but it has **not been visually tested** end-to-end. Steps:

```bash
# Terminal 1 — backend
cd backend && ./.venv/bin/uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev

# Then open http://localhost:5173/sepa
```

Verify:
- Hero strip color codes correctly (green/amber/red by market regime)
- Top-picks rail renders with rating colors
- Filter chips toggle correctly
- Card grid populates with score bars + trend dots
- Clicking a card opens the slide-in drawer with 5 tabs
- Setup tab shows the R-multiple ladder + live position planner
- Mobile responsive at <720px

**If the brief banner stays empty:** the brief.json hasn't been generated. Run:
```bash
cd backend && ./.venv/bin/python -m sepa.cli scan
cd backend && ./.venv/bin/python -m sepa.cli brief
```

---

## 2. What's been built this session (do NOT redo)

### Backend: 5 missing-logic gaps closed

| Module | What it does | Why |
|---|---|---|
| `backend/sepa/adr.py` (NEW) | ADR% (20-day) + `liquidity_check` ($20M $-vol or 200k shares) | cookstock parity; rejects un-tradeable thin names |
| `backend/sepa/canslim.py` (NEW) | C/A/I checks via yfinance: Q EPS ≥25%, Y EPS ≥25%, inst 40-80% | xang1234 parity; runs in catalyst phase, score-bumps top 20 candidates |
| `backend/sepa/vcp.py` (PATCHED) | Added `pivot_quality_ok` (≥20% prior advance), shrinkage 0.75 (was 1.10), lookback 325d (was 90d) | cookstock pivot quality + book p.199, p.212 |
| `backend/sepa/scanner.py` (PATCHED) | Score normalized 0-100, emits `rating: STRONG_BUY/BUY/WATCH/NEUTRAL/AVOID`; gates on liquidity; carries `adr_pct`, `liquidity` fields | xang1234 parity; UI needs the rating field |
| `backend/sepa/risk.py` (PATCHED) | Warn threshold tightened from 8% to 7% (book p.276) | spec verifier finding |

### Backend: 5 spec-vs-book mismatches fixed

See `SPECS_VERIFIED.md` § Critical Mismatches. All applied to code.

### Frontend: SEPA UI v2

New files:
- `frontend/src/components/SepaHero.tsx` — color-coded market regime + stats + scan actions
- `frontend/src/components/SepaFilterBar.tsx` — rating chips, setup chips, RS slider, search, sort
- `frontend/src/components/SepaCandidateCard.tsx` — card grid (replaces table)
- `frontend/src/components/SepaScoreBar.tsx` — visual 0-100 score, color by tier
- `frontend/src/components/SepaTrendDots.tsx` — 8 mini dots per Trend Template criterion

Rewritten:
- `frontend/src/pages/Sepa.tsx` — top-picks rail + filter bar + card grid
- `frontend/src/components/SepaCandidateModal.tsx` — slide-in drawer w/ 5 tabs (setup / trend / fundamentals / catalyst / insider), R-multiple ladder, live position planner

CSS: ~280 new lines appended to `frontend/src/styles.css` under `/* SEPA v2 */` comment block.

### Docs

- `SPECS.md` — 607 lines, full system spec (10 sections)
- `SPECS_VERIFIED.md` — 21 thresholds verified against PDF pages with quotes; 9 still UNVERIFIED (in Ch.6 + Ch.14, agent didn't open those)
- `graphify-out/graph.html` — 300 nodes, 346 edges, 44 communities
- `graphify-out/GRAPH_REPORT.md` — plain-language report

---

## 3. Critical context (don't lose this)

### Polygon.io rebranded to Massive (Oct 30, 2025)
`api.polygon.io` and `api.massive.com` both work. Same company. **Don't recommend Massive as a Polygon alternative — it IS Polygon.** This is an actual fact-check failure I made earlier in the session; user called it out and was right to.

### Independent vendor alternatives (real hedges)
Tiingo, Alpaca, Databento, EODHD, Twelve Data, FMP. Polygon.io / Massive is the same vendor. The IEX Cloud shutdown (2024) is a cautionary tale — picking a `MarketDataProvider` interface beats picking a vendor.

### Provider abstraction (planned, not done)
`backend/sepa/providers.py` has `has_polygon()` / `has_finnhub()` toggles but no real adapter. The day you want to flip from yfinance → Massive, define a `MarketDataProvider` Protocol with `get_bars`, `get_quote`, `stream_trades`, then implement `YFinanceProvider` and `MassiveProvider`. `scanner._analyze_symbol` should take `provider:` as a dep.

### What's NOT verified against the book
9 thresholds in `sell_signals.py` (climax +25%/3w, biggest-decline rules, <50MA-on-vol, <200MA exit) and `ipo_age.py`. The verifier did not open Ch.6 (Fundamentals) or Ch.14 (Selling). **Open those chapters before trusting those modules with real money.**

### Author heuristics (NOT in book)
Honest list — these are reasonable engineer choices, not Minervini-sourced:
- composite score weights (30/25/15/10/10/5/5)
- rating tier cutoffs (85/70/60/40)
- ADR ≥4% (industry standard)
- liquidity floor ($20M / 200k shares)
- RS rank weights 40/20/20/20 (IBD/O'Neil)
- volume multipliers (1.3×, 1.5×, 0.7)
- VCP pivot-quality 20% (cookstock heuristic)
- catalyst keyword sets
- insider cluster threshold (≥3 unique insiders / 30d)

### Security TODO from spec audit
`backend/.env` may contain a live Finnhub key. Verify and rotate if true. Never commit it.

### Known frontend dead code (per spec audit)
- `frontend/src/pages/Dashboard.tsx` — not routed
- `useSepa.ts` hardcodes `http://localhost:8000` — vite proxy has no `/sepa/*` entry; works for dev, breaks in prod. Either add a proxy entry or use env var (with proper TS types this time, not `import.meta.env`).
- `cli rescan` only refreshes parquet cache, not `latest.json`

---

## 4. Architecture at a glance

### Backend file map
```
backend/
├── main.py                  # FastAPI app + 9 SEPA endpoints + Finnhub WS
├── .env                     # SEC_USER_AGENT, FINNHUB_API_KEY (verify clean)
└── sepa/
    ├── adr.py               # NEW — ADR + liquidity
    ├── base_count.py        # base counting (1st/2nd/late stage)
    ├── brief.py             # morning brief generator
    ├── canslim.py           # NEW — C/A/I fundamentals
    ├── catalyst.py          # earnings, news sentiment, analyst revs
    ├── cli.py               # `python -m sepa.cli scan|brief|rescan`
    ├── insider.py           # EDGAR Form 4 / 13D / 13G
    ├── ipo_age.py           # young/recent IPO flag
    ├── market_context.py    # SPY+QQQ trend gate
    ├── minervini.pdf        # source of truth (KEEP)
    ├── power_play.py        # +100%/8wk + ≤25% digest
    ├── prices.py            # yfinance + parquet cache
    ├── providers.py         # has_polygon() / has_finnhub() toggles
    ├── risk.py              # position sizing, R-multiples
    ├── rs_rank.py           # IBD-style RS percentile
    ├── scanner.py           # orchestrator + composite score 0-100
    ├── sell_signals.py      # 7 sell signals → action label
    ├── stage.py             # 4-stage classifier
    ├── trend_template.py    # 8-criteria template
    ├── universe.py          # ticker list (env-overridable)
    ├── vcp.py               # PATCHED — pivot quality + 325d lookback
    └── volume.py            # up/down vol, dryup, hi-vol breakout
```

### Frontend file map (post-changes)
```
frontend/src/
├── App.tsx                              # remove /india route in next session
├── styles.css                           # SEPA v2 CSS at the bottom
├── hooks/
│   ├── useSepa.ts                       # Rating type + new fields added
│   └── useCheetahStocks.ts
├── components/
│   ├── NavBar.tsx                       # remove India link in next session
│   ├── SepaHero.tsx                     # NEW
│   ├── SepaFilterBar.tsx                # NEW
│   ├── SepaCandidateCard.tsx            # NEW
│   ├── SepaScoreBar.tsx                 # NEW
│   ├── SepaTrendDots.tsx                # NEW
│   ├── SepaCandidateModal.tsx           # REWRITTEN as drawer w/ tabs
│   └── SepaBriefBanner.tsx              # unchanged
└── pages/
    ├── Sepa.tsx                         # REWRITTEN
    └── ModernDashboard.tsx              # remove India section in next session
```

### Endpoints (`backend/main.py`)
```
GET   /sepa/scan
POST  /sepa/scan?no_catalyst=bool
GET   /sepa/brief
POST  /sepa/brief
GET   /sepa/candidate/{symbol}
POST  /sepa/rescan/{symbol}
GET   /sepa/watchlist
POST  /sepa/watchlist?symbol=&entry=&stop=
DELETE /sepa/watchlist/{symbol}
POST  /sepa/position-plan?entry=&stop=&account_size=&risk_per_trade_pct=
```

### launchd jobs
```
launchd/com.cheetah.sepa.scan.plist    # Mon-Fri 17:00 → sepa.cli scan
launchd/com.cheetah.sepa.brief.plist   # Mon-Fri 08:30 → sepa.cli brief
```
Install instructions in `launchd/README.md`. **Note:** launchd does NOT inherit shell env — set `EnvironmentVariables` in the plist for `FINNHUB_API_KEY` / `SEC_USER_AGENT`.

---

## 5. Suggested next-session order of operations

1. **Read this file + `SPECS_VERIFIED.md` Critical Mismatches section** (5 min)
2. **Strip India** — delete files, edit App / NavBar / ModernDashboard, run `tsc -b --noEmit` (15 min)
3. **Boot the app** — backend uvicorn + frontend vite, hit `/sepa`, verify the new UI loads (10 min)
4. **Run a fresh scan** with catalyst enrichment to populate fundamentals + ratings (5 min)
5. **Visual QA** — check hero colors, top-picks rail, card grid, drawer tabs, R-ladder (15 min)
6. **Fix any visual bugs** (variable)
7. **Decide on Polygon/Massive provider abstraction** — when ready, do the `MarketDataProvider` Protocol refactor

---

## 6. Backlog (deferred but tracked)

- **Provider abstraction** — `MarketDataProvider` Protocol; YFinance + Massive adapters; inject into scanner
- **Open Ch.14 + Ch.6 of Minervini PDF** — verify the 9 unverified thresholds in `sell_signals.py` and `ipo_age.py`
- **Sparkline charts** — current UI has no price/volume mini-charts; would massively help glance-readability. Inline SVG, no dep needed.
- **Watchlist sidebar on /sepa page** — currently watchlist only surfaces in morning brief. Add a sticky sidebar showing held positions with live distance-to-stop.
- **Tests** — there are zero tests anywhere. At minimum, snapshot test `_analyze_symbol` on a known-good ticker so future refactors don't silently break the gate stack.
- **Production deploy story** — currently dev-only. CORS, frontend env vars, prod build, hosting all undecided.
- **`api.polygon.io` → `api.massive.com`** — once provider abstraction lands, switch base URL. No urgency; both still work.
- **EDGAR 8-K earnings calendar** — would let us drop Finnhub dependency entirely (one less vendor).

---

## 7. Useful one-liners

```bash
# Run a scan from CLI
cd backend && ./.venv/bin/python -m sepa.cli scan

# Re-analyze one symbol with fresh price data
cd backend && ./.venv/bin/python -m sepa.cli rescan NVDA

# Generate morning brief
cd backend && ./.venv/bin/python -m sepa.cli brief

# Type-check frontend
cd frontend && npx tsc -b --noEmit

# Boot backend dev
cd backend && ./.venv/bin/uvicorn main:app --reload --port 8000

# Boot frontend dev
cd frontend && npm run dev

# Inspect graph
open graphify-out/graph.html
```
