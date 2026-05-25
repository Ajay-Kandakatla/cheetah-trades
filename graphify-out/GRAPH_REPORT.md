# Graph Report - /Users/ajay/clinet-test/cheetah-market-app  (2026-04-28)

## Corpus Check
- 93 files · ~106,416 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 718 nodes · 1112 edges · 72 communities detected
- Extraction: 74% EXTRACTED · 26% INFERRED · 0% AMBIGUOUS · INFERRED: 290 edges (avg confidence: 0.76)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Backend API Routes|Backend API Routes]]
- [[_COMMUNITY_Architecture & Handoff Notes|Architecture & Handoff Notes]]
- [[_COMMUNITY_Chatter & Insider News|Chatter & Insider News]]
- [[_COMMUNITY_SEPA CLI Entrypoints|SEPA CLI Entrypoints]]
- [[_COMMUNITY_Liquidity & ADR Filters|Liquidity & ADR Filters]]
- [[_COMMUNITY_Position Alerts & Brief|Position Alerts & Brief]]
- [[_COMMUNITY_Frontend Hooks & Helpers|Frontend Hooks & Helpers]]
- [[_COMMUNITY_Stock Analysis Panel|Stock Analysis Panel]]
- [[_COMMUNITY_IPO Age Filter|IPO Age Filter]]
- [[_COMMUNITY_Base Count & Market Context|Base Count & Market Context]]
- [[_COMMUNITY_Cheetah Dashboard Components|Cheetah Dashboard Components]]
- [[_COMMUNITY_Mongo Scan History|Mongo Scan History]]
- [[_COMMUNITY_Catalyst Detection|Catalyst Detection]]
- [[_COMMUNITY_Pioneers Theme Ranker|Pioneers Theme Ranker]]
- [[_COMMUNITY_launchd  Cron Brief|launchd / Cron Brief]]
- [[_COMMUNITY_CANSLIM Fundamentals|CANSLIM Fundamentals]]
- [[_COMMUNITY_Docker Deploy Topology|Docker Deploy Topology]]
- [[_COMMUNITY_Indian Market Data|Indian Market Data]]
- [[_COMMUNITY_Live Quote Row|Live Quote Row]]
- [[_COMMUNITY_Theme Toggle|Theme Toggle]]
- [[_COMMUNITY_VCP Pattern Detector|VCP Pattern Detector]]
- [[_COMMUNITY_Frontend Shell & Fonts|Frontend Shell & Fonts]]
- [[_COMMUNITY_Indian Stock Table|Indian Stock Table]]
- [[_COMMUNITY_Company Headline|Company Headline]]
- [[_COMMUNITY_Stock Analysis Panel UI|Stock Analysis Panel UI]]
- [[_COMMUNITY_SEPA Scan Progress|SEPA Scan Progress]]
- [[_COMMUNITY_Enhanced Indian Stock Table|Enhanced Indian Stock Table]]
- [[_COMMUNITY_Indian Market Page|Indian Market Page]]
- [[_COMMUNITY_LiveStream Page|LiveStream Page]]
- [[_COMMUNITY_Indian Market Indices|Indian Market Indices]]
- [[_COMMUNITY_Indian News Panel|Indian News Panel]]
- [[_COMMUNITY_Symbol Search|Symbol Search]]
- [[_COMMUNITY_Watchlist Section|Watchlist Section]]
- [[_COMMUNITY_Info Button|Info Button]]
- [[_COMMUNITY_SEPA Scan SSE Stream|SEPA Scan SSE Stream]]
- [[_COMMUNITY_Chatter Page|Chatter Page]]
- [[_COMMUNITY_Dual Momentum Component|Dual Momentum Component]]
- [[_COMMUNITY_Pioneers Page|Pioneers Page]]
- [[_COMMUNITY_India Strip Task|India Strip Task]]
- [[_COMMUNITY_Env Vars & Key Rotation|Env Vars & Key Rotation]]
- [[_COMMUNITY_App Root|App Root]]
- [[_COMMUNITY_SEPA Score Bar|SEPA Score Bar]]
- [[_COMMUNITY_Nav Bar|Nav Bar]]
- [[_COMMUNITY_SEPA Candidate Card|SEPA Candidate Card]]
- [[_COMMUNITY_On-Demand SEPA Modal|On-Demand SEPA Modal]]
- [[_COMMUNITY_Chatter Panel|Chatter Panel]]
- [[_COMMUNITY_Sparkline|Sparkline]]
- [[_COMMUNITY_SEPA Trend Dots|SEPA Trend Dots]]
- [[_COMMUNITY_Chatter India Panel|Chatter India Panel]]
- [[_COMMUNITY_Stock Detail Modal|Stock Detail Modal]]
- [[_COMMUNITY_Indicators Card|Indicators Card]]
- [[_COMMUNITY_Market Stream Hook|Market Stream Hook]]
- [[_COMMUNITY_SEPA Page|SEPA Page]]
- [[_COMMUNITY_Modern Dashboard|Modern Dashboard]]
- [[_COMMUNITY_SEPA Module Init|SEPA Module Init]]
- [[_COMMUNITY_Graphify Finish|Graphify Finish]]
- [[_COMMUNITY_Dead Code & Gaps|Dead Code & Gaps]]
- [[_COMMUNITY_SEPA Candidate Modal|SEPA Candidate Modal]]
- [[_COMMUNITY_Vite Dev Proxy|Vite Dev Proxy]]
- [[_COMMUNITY_SSE Stream Endpoint|SSE Stream Endpoint]]
- [[_COMMUNITY_Vite Config|Vite Config]]
- [[_COMMUNITY_Main Entry|Main Entry]]
- [[_COMMUNITY_Shared Types|Shared Types]]
- [[_COMMUNITY_SEPA Brief Banner|SEPA Brief Banner]]
- [[_COMMUNITY_Theme Toggle Component|Theme Toggle Component]]
- [[_COMMUNITY_Watchlist Data|Watchlist Data]]
- [[_COMMUNITY_Chatter India Page|Chatter India Page]]
- [[_COMMUNITY_News Aggregation|News Aggregation]]
- [[_COMMUNITY_Data Flow Diagrams|Data Flow Diagrams]]
- [[_COMMUNITY_Spec-Driven Dev|Spec-Driven Dev]]
- [[_COMMUNITY_Provenance Map|Provenance Map]]
- [[_COMMUNITY_Backlog Items|Backlog Items]]

## God Nodes (most connected - your core abstractions)
1. `get()` - 83 edges
2. `ProgressEmitter` - 53 edges
3. `SEPA module (backend/sepa/*)` - 29 edges
4. `load_prices()` - 18 edges
5. `scanner.py orchestrator` - 18 edges
6. `backend/requirements.txt` - 14 edges
7. `run()` - 13 edges
8. `main()` - 13 edges
9. `_analyze_symbol()` - 12 edges
10. `scan_universe_fast()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `VCP - Volatility Contraction Pattern` --semantically_similar_to--> `vcp.py`  [INFERRED] [semantically similar]
  SPECS_VERIFIED.md → SPECS.md
- `cheetah_data.py — Data + Cheetah Score Engine` --implements--> `18 Tier 1 Cheetah Stocks`  [EXTRACTED]
  backend/cheetah_data.py → KNOWLEDGE_BASE.md
- `cheetah_data.py — Data + Cheetah Score Engine` --implements--> `Private Unicorns with Public Proxies (12 companies)`  [EXTRACTED]
  backend/cheetah_data.py → KNOWLEDGE_BASE.md
- `cheetah_data.py — Data + Cheetah Score Engine` --implements--> `Competitor Scout Groups (NVDA/CRDO peers)`  [EXTRACTED]
  backend/cheetah_data.py → KNOWLEDGE_BASE.md
- `Trend Template (8 criteria)` --semantically_similar_to--> `trend_template.py`  [INFERRED] [semantically similar]
  SPECS_VERIFIED.md → SPECS.md

## Hyperedges (group relationships)
- **Cheetah launchd SEPA pipeline** — readme_scan_plist, readme_brief_plist, readme_latest_json, readme_brief_json, readme_sepa_cli [EXTRACTED 1.00]
- **SEPA core pillars** — minervini_trend_template, minervini_vcp, minervini_power_play, minervini_rs_rank, minervini_risk_rules [INFERRED 0.85]
- **Four-stage market cycle** — minervini_stage_1, minervini_stage_2, minervini_stage_3, minervini_stage_4 [EXTRACTED 1.00]
- **SEPA scanner pipeline** —  [EXTRACTED 1.00]
- **Docker compose 4-service stack** —  [EXTRACTED 1.00]
- **Minervini book threshold provenance** —  [EXTRACTED 1.00]

## Communities

### Community 0 - "Backend API Routes"
Cohesion: 0.03
Nodes (86): load_brief(), cheetah(), _company_profile(), competitors(), etfs(), finnhub_rest_poller(), finnhub_ws_consumer(), health() (+78 more)

### Community 1 - "Architecture & Handoff Notes"
Cohesion: 0.05
Nodes (68): Rationale: rotate Massive key (compromised), Polygon = Massive (Oct 2025 rebrand), Planned MarketDataProvider Protocol, Live Stream (SSE + Finnhub WS), Price Alerts (per-symbol triggers), SEPA Screen feature, Stack: FastAPI + React + supercronic + Mongo, beautifulsoup4==4.14.3 (+60 more)

### Community 2 - "Chatter & Insider News"
Cohesion: 0.06
Nodes (60): chatter_for(), chatter_universe(), _get_cache(), _hacker_news(), _now(), Forum Chatter — crowd discussion across stock-focused portals.  Four lanes per t, Per-ticker chatter payload. Cached 15 min in Mongo., Universe-wide ranking by mention velocity.      Returns rows for every symbol — (+52 more)

### Community 3 - "SEPA CLI Entrypoints"
Cohesion: 0.05
Nodes (45): main(), SEPA command-line entrypoints — invoked by launchd cron jobs.  Usage:     python, bulk_warm(), _fetch_yfinance(), _get_mongo(), _mongo_get(), _mongo_put(), Company name resolver — symbol → human-readable company name.  Used by the SEPA (+37 more)

### Community 4 - "Liquidity & ADR Filters"
Cohesion: 0.06
Nodes (42): adr_pct(), liquidity_check(), ADR — Average Daily Range (20-period).  A liquidity/volatility quality filter Mi, Return ADR% over `period` bars, or None if insufficient data., Institutional-grade liquidity check.      Minervini: avoid thin stocks — institu, name_for(), Return the cached company name for a symbol, or None if unknown.      Does NOT t, _benchmark_return() (+34 more)

### Community 5 - "Position Alerts & Brief"
Cohesion: 0.09
Nodes (32): _alert_state_coll(), check_positions(), _last_fired(), _mark_fired(), Intraday position alerts — runs every few minutes during market hours.  For each, generate_brief(), Morning brief — "what to watch when I open the app at 8:30am".  Consumes the 5pm, _watchlist_status() (+24 more)

### Community 6 - "Frontend Hooks & Helpers"
Cohesion: 0.09
Nodes (19): rescan(), set(), handleResearchRefresh(), _cache_path(), fetch_russell1000(), fetch_sp500(), load_universe(), Scanning universe — tickers we run SEPA against.  Three modes, selected via the (+11 more)

### Community 7 - "Stock Analysis Panel"
Cohesion: 0.13
Nodes (26): analysis_for(), analyst_panel(), _cache_get(), _cache_put(), _clip(), _empty_fundamentals(), _empty_technical(), _esg_label() (+18 more)

### Community 8 - "IPO Age Filter"
Cohesion: 0.13
Nodes (21): age(), IPO-age filter — young companies preferred (Ch 11).  "80% of 1990s winners were, _cache_path(), _fetch(), _fetch_massive(), _fetch_yfinance(), _get_mongo(), load_prices() (+13 more)

### Community 9 - "Base Count & Market Context"
Cohesion: 0.08
Nodes (25): backend/sepa/base_count.py, backend/sepa/market_context.py, Base Count (1st, 2nd, 3rd stage bases), 4 Stages of a Stock, Leadership stocks in strong groups, Market Context / General Market Health, Trade Like a Stock Market Wizard (Minervini), Pivot Point Buy (+17 more)

### Community 10 - "Cheetah Dashboard Components"
Cohesion: 0.11
Nodes (23): cheetah_data.py — Data + Cheetah Score Engine, CheetahTable.tsx — Sortable/Filterable Stock Table, CompetitorScoutCard.tsx — NVDA/CRDO Peer Comparison, EtfsCard.tsx — Thematic ETFs, FormulaCard.tsx — Cheetah Score Formula Display, NewsPanel.tsx — Aggregated Headlines, RefreshButton.tsx — Triggers /cheetah Recompute, UnicornsCard.tsx — Private Unicorn Proxies (+15 more)

### Community 11 - "Mongo Scan History"
Cohesion: 0.22
Nodes (14): diff_dates(), _eastern_date(), _get_db(), get_recent_runs(), get_scan_by_date(), get_symbol_history(), MongoDB-backed scan history.  Persists every scan run + per-candidate snapshot s, Trajectory of one symbol over the last `days` days. (+6 more)

### Community 12 - "Catalyst Detection"
Cohesion: 0.19
Nodes (10): catalyst_for(), _fetch_finnhub_earnings(), _fetch_google_news(), _fetch_yfinance_extras(), Catalyst detection — what could move a SEPA candidate today.  Three inputs:   1., Synchronous — run in a thread via asyncio., Fetch ticker-relevant news headlines.      Two-step strategy to avoid the USD-as, _score_headline() (+2 more)

### Community 13 - "Pioneers Theme Ranker"
Cohesion: 0.21
Nodes (11): _coll(), _fetch_news_for(), pioneers_for_scan(), Pioneers — breakthrough-news ranker that runs alongside the SEPA scan.  Two outp, Per-headline breakthrough score. 0 if not breakthrough-flavored.      Universal, Per-ticker news fetch + scoring. Returns {score, count, top_headlines}., Build the Pioneers payload from a SEPA scan's rows.      Args:         scan_rows, All symbols that appear in at least one theme — used by SEPA filter. (+3 more)

### Community 14 - "launchd / Cron Brief"
Cohesion: 0.24
Nodes (10): ~/.cheetah/scans/brief.json, com.cheetah.sepa.brief.plist, Mon-Fri 8:30am morning brief, ~/.cheetah/scans/latest.json, launchctl load/unload/start, launchd/README.md, Polygon API integration, com.cheetah.sepa.scan.plist (+2 more)

### Community 15 - "CANSLIM Fundamentals"
Cohesion: 0.36
Nodes (8): _empty(), fundamentals_for(), _inst_ownership(), _q_eps_growth(), CANSLIM-style fundamentals layer.  Minervini's "S" (Specific entry-point setups, Return CANSLIM-style fundamentals snapshot for a symbol.      Output shape (all, _rev_q_growth(), _y_eps_growth()

### Community 16 - "Docker Deploy Topology"
Cohesion: 0.22
Nodes (7): docker-compose 4 services, Cron schedule (NY tz), LAN exposure / hardening notes, Volumes mongo-data + cheetah-scans, Docker deployment (production), Scheduled jobs (supercronic+launchd), Rationale: init:true + absolute python path

### Community 17 - "Indian Market Data"
Cohesion: 0.36
Nodes (7): _build_index(), _build_stock(), fetch_indian_market(), _fetch_yahoo_chart(), Real-time Indian market data from Yahoo Finance (free, no API key).  Uses Yahoo', Fetch all stocks + indices in parallel with a short-lived cache., Hit Yahoo's free chart endpoint. Returns the `meta` object or None.

### Community 18 - "Live Quote Row"
Cohesion: 0.33
Nodes (0): 

### Community 19 - "Theme Toggle"
Cohesion: 0.47
Nodes (3): readStoredTheme(), resolveInitial(), systemPrefersDark()

### Community 20 - "VCP Pattern Detector"
Cohesion: 0.4
Nodes (5): detect(), _find_swings(), VCP — Volatility Contraction Pattern detector.  Book Ch 10 (p.198-213):   - Base, Return [(idx, price, 'H'|'L'), ...] using simple local-extrema rule., Detect a VCP in the last `lookback_days` bars. Returns None if no     discernibl

### Community 21 - "Frontend Shell & Fonts"
Cohesion: 0.33
Nodes (6): SEPA UI v2 (Hero/FilterBar/Cards/Drawer), frontend/index.html shell, Google Fonts (Inter + JetBrains Mono), #root + main.tsx entry, Curated Cheetah Dashboard, Frontend (React/Vite/TS)

### Community 22 - "Indian Stock Table"
Cohesion: 0.4
Nodes (0): 

### Community 23 - "Company Headline"
Cohesion: 0.4
Nodes (0): 

### Community 24 - "Stock Analysis Panel UI"
Cohesion: 0.4
Nodes (0): 

### Community 25 - "SEPA Scan Progress"
Cohesion: 0.4
Nodes (0): 

### Community 26 - "Enhanced Indian Stock Table"
Cohesion: 0.5
Nodes (0): 

### Community 27 - "Indian Market Page"
Cohesion: 0.5
Nodes (2): IndianMarket(), useIndianStocks()

### Community 28 - "LiveStream Page"
Cohesion: 0.5
Nodes (0): 

### Community 29 - "Indian Market Indices"
Cohesion: 0.67
Nodes (0): 

### Community 30 - "Indian News Panel"
Cohesion: 1.0
Nodes (2): IndianNewsPanel(), relativeTime()

### Community 31 - "Symbol Search"
Cohesion: 0.67
Nodes (0): 

### Community 32 - "Watchlist Section"
Cohesion: 0.67
Nodes (0): 

### Community 33 - "Info Button"
Cohesion: 0.67
Nodes (0): 

### Community 34 - "SEPA Scan SSE Stream"
Cohesion: 0.67
Nodes (0): 

### Community 35 - "Chatter Page"
Cohesion: 0.67
Nodes (0): 

### Community 36 - "Dual Momentum Component"
Cohesion: 0.67
Nodes (0): 

### Community 37 - "Pioneers Page"
Cohesion: 0.67
Nodes (0): 

### Community 38 - "India Strip Task"
Cohesion: 0.67
Nodes (3): Open task: build UI, US-only, Strip India-market features, Indian market panel

### Community 39 - "Env Vars & Key Rotation"
Cohesion: 0.67
Nodes (3): Rotate Finnhub key in backend/.env, Required env keys (Finnhub/Massive/Mongo/Twilio), Env vars table

### Community 40 - "App Root"
Cohesion: 1.0
Nodes (0): 

### Community 41 - "SEPA Score Bar"
Cohesion: 1.0
Nodes (0): 

### Community 42 - "Nav Bar"
Cohesion: 1.0
Nodes (0): 

### Community 43 - "SEPA Candidate Card"
Cohesion: 1.0
Nodes (0): 

### Community 44 - "On-Demand SEPA Modal"
Cohesion: 1.0
Nodes (0): 

### Community 45 - "Chatter Panel"
Cohesion: 1.0
Nodes (0): 

### Community 46 - "Sparkline"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "SEPA Trend Dots"
Cohesion: 1.0
Nodes (0): 

### Community 48 - "Chatter India Panel"
Cohesion: 1.0
Nodes (0): 

### Community 49 - "Stock Detail Modal"
Cohesion: 1.0
Nodes (0): 

### Community 50 - "Indicators Card"
Cohesion: 1.0
Nodes (0): 

### Community 51 - "Market Stream Hook"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "SEPA Page"
Cohesion: 1.0
Nodes (0): 

### Community 53 - "Modern Dashboard"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "SEPA Module Init"
Cohesion: 1.0
Nodes (1): Minervini SEPA — screener, morning brief, catalyst + insider signals.

### Community 55 - "Graphify Finish"
Cohesion: 1.0
Nodes (1): Finalize graphify pipeline: cluster, label, viz, report, JSON.

### Community 56 - "Dead Code & Gaps"
Cohesion: 1.0
Nodes (2): Known frontend dead code, Known gaps / TODOs

### Community 57 - "SEPA Candidate Modal"
Cohesion: 1.0
Nodes (0): 

### Community 58 - "Vite Dev Proxy"
Cohesion: 1.0
Nodes (1): Vite Dev Proxy (port 5173 → 8000)

### Community 59 - "SSE Stream Endpoint"
Cohesion: 1.0
Nodes (1): Server-Sent Events /stream Endpoint

### Community 60 - "Vite Config"
Cohesion: 1.0
Nodes (0): 

### Community 61 - "Main Entry"
Cohesion: 1.0
Nodes (0): 

### Community 62 - "Shared Types"
Cohesion: 1.0
Nodes (0): 

### Community 63 - "SEPA Brief Banner"
Cohesion: 1.0
Nodes (0): 

### Community 64 - "Theme Toggle Component"
Cohesion: 1.0
Nodes (0): 

### Community 65 - "Watchlist Data"
Cohesion: 1.0
Nodes (0): 

### Community 66 - "Chatter India Page"
Cohesion: 1.0
Nodes (0): 

### Community 67 - "News Aggregation"
Cohesion: 1.0
Nodes (1): news.py — News Aggregation

### Community 68 - "Data Flow Diagrams"
Cohesion: 1.0
Nodes (1): Data flow diagrams

### Community 69 - "Spec-Driven Dev"
Cohesion: 1.0
Nodes (1): Spec-Driven Development (spec-kit)

### Community 70 - "Provenance Map"
Cohesion: 1.0
Nodes (1): Provenance Map

### Community 71 - "Backlog Items"
Cohesion: 1.0
Nodes (1): Backlog (provider abstraction, tests, sparkline)

## Knowledge Gaps
- **179 isolated node(s):** `CheetahTable.tsx — Sortable/Filterable Stock Table`, `NewsPanel.tsx — Aggregated Headlines`, `CompetitorScoutCard.tsx — NVDA/CRDO Peer Comparison`, `EtfsCard.tsx — Thematic ETFs`, `UnicornsCard.tsx — Private Unicorn Proxies` (+174 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `App Root`** (2 nodes): `App()`, `App.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `SEPA Score Bar`** (2 nodes): `SepaScoreBar()`, `SepaScoreBar.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Nav Bar`** (2 nodes): `NavBar()`, `NavBar.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `SEPA Candidate Card`** (2 nodes): `SepaCandidateCard()`, `SepaCandidateCard.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `On-Demand SEPA Modal`** (2 nodes): `setStepPhase()`, `OnDemandSepaModal.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Chatter Panel`** (2 nodes): `timeAgo()`, `ChatterPanel.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Sparkline`** (2 nodes): `Sparkline.tsx`, `Sparkline()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `SEPA Trend Dots`** (2 nodes): `SepaTrendDots()`, `SepaTrendDots.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Chatter India Panel`** (2 nodes): `timeAgo()`, `ChatterIndiaPanel.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Stock Detail Modal`** (2 nodes): `StockDetailModal.tsx`, `onKey()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Indicators Card`** (2 nodes): `IndicatorsCard()`, `IndicatorsCard.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Market Stream Hook`** (2 nodes): `useMarketStream()`, `useMarketStream.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `SEPA Page`** (2 nodes): `openSymbol()`, `Sepa.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Modern Dashboard`** (2 nodes): `ModernDashboard()`, `ModernDashboard.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `SEPA Module Init`** (2 nodes): `__init__.py`, `Minervini SEPA — screener, morning brief, catalyst + insider signals.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Graphify Finish`** (2 nodes): `Finalize graphify pipeline: cluster, label, viz, report, JSON.`, `_finish.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Dead Code & Gaps`** (2 nodes): `Known frontend dead code`, `Known gaps / TODOs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `SEPA Candidate Modal`** (1 nodes): `SepaCandidateModal.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Vite Dev Proxy`** (1 nodes): `Vite Dev Proxy (port 5173 → 8000)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `SSE Stream Endpoint`** (1 nodes): `Server-Sent Events /stream Endpoint`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Vite Config`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Main Entry`** (1 nodes): `main.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Shared Types`** (1 nodes): `types.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `SEPA Brief Banner`** (1 nodes): `SepaBriefBanner.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Theme Toggle Component`** (1 nodes): `ThemeToggle.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Watchlist Data`** (1 nodes): `watchlist.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Chatter India Page`** (1 nodes): `ChatterIndia.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `News Aggregation`** (1 nodes): `news.py — News Aggregation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Data Flow Diagrams`** (1 nodes): `Data flow diagrams`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Spec-Driven Dev`** (1 nodes): `Spec-Driven Development (spec-kit)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Provenance Map`** (1 nodes): `Provenance Map`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Backlog Items`** (1 nodes): `Backlog (provider abstraction, tests, sparkline)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get()` connect `Chatter & Insider News` to `Backend API Routes`, `SEPA CLI Entrypoints`, `Liquidity & ADR Filters`, `Position Alerts & Brief`, `Stock Analysis Panel`, `IPO Age Filter`, `Mongo Scan History`, `Catalyst Detection`, `Pioneers Theme Ranker`, `CANSLIM Fundamentals`?**
  _High betweenness centrality (0.238) - this node is a cross-community bridge._
- **Why does `ProgressEmitter` connect `Backend API Routes` to `IPO Age Filter`, `Chatter & Insider News`, `SEPA CLI Entrypoints`, `Liquidity & ADR Filters`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `set()` connect `Frontend Hooks & Helpers` to `Chatter & Insider News`, `SEPA CLI Entrypoints`, `Pioneers Theme Ranker`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `get()` (e.g. with `.hydrate_from_mongo()` and `.update()`) actually correct?**
  _`get()` has 80 INFERRED edges - model-reasoned connections that need verification._
- **Are the 47 inferred relationships involving `ProgressEmitter` (e.g. with `QuoteCache` and `Market Stream — FastAPI Server-Sent Events backend.  Streams real-time quotes +`) actually correct?**
  _`ProgressEmitter` has 47 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `load_prices()` (e.g. with `check_positions()` and `_analyze_symbol()`) actually correct?**
  _`load_prices()` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `CheetahTable.tsx — Sortable/Filterable Stock Table`, `NewsPanel.tsx — Aggregated Headlines`, `CompetitorScoutCard.tsx — NVDA/CRDO Peer Comparison` to the rest of the system?**
  _179 weakly-connected nodes found - possible documentation gaps or missing edges._