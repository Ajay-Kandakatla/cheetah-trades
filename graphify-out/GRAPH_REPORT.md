# Graph Report - /Users/ajay/clinet-test/cheetah-market-app  (2026-04-21)

## Corpus Check
- Corpus is ~11,196 words - fits in a single context window. You may not need a graph.

## Summary
- 135 nodes · 154 edges · 26 communities detected
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.84)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_FastAPI Backend Core|FastAPI Backend Core]]
- [[_COMMUNITY_Data + Research Concepts|Data + Research Concepts]]
- [[_COMMUNITY_Real-Time Streaming|Real-Time Streaming]]
- [[_COMMUNITY_Cheetah Score Engine|Cheetah Score Engine]]
- [[_COMMUNITY_News Aggregation|News Aggregation]]
- [[_COMMUNITY_Dashboard Components|Dashboard Components]]
- [[_COMMUNITY_Table Utilities|Table Utilities]]
- [[_COMMUNITY_ETF & Unicorn Cards|ETF & Unicorn Cards]]
- [[_COMMUNITY_Dashboard Page + Hook|Dashboard Page + Hook]]
- [[_COMMUNITY_Refresh Button|Refresh Button]]
- [[_COMMUNITY_Quote Row Display|Quote Row Display]]
- [[_COMMUNITY_News Panel|News Panel]]
- [[_COMMUNITY_Live Stream Page|Live Stream Page]]
- [[_COMMUNITY_App Router|App Router]]
- [[_COMMUNITY_Navigation Bar|Navigation Bar]]
- [[_COMMUNITY_Formula Card|Formula Card]]
- [[_COMMUNITY_Sparkline Chart|Sparkline Chart]]
- [[_COMMUNITY_Indicators Card|Indicators Card]]
- [[_COMMUNITY_Market Stream Hook|Market Stream Hook]]
- [[_COMMUNITY_Vite Config|Vite Config]]
- [[_COMMUNITY_App Entry Point|App Entry Point]]
- [[_COMMUNITY_TypeScript Types|TypeScript Types]]
- [[_COMMUNITY_Competitor Scout Card|Competitor Scout Card]]
- [[_COMMUNITY_Python Dependencies|Python Dependencies]]
- [[_COMMUNITY_Styles|Styles]]
- [[_COMMUNITY_NavBar Component|NavBar Component]]

## God Nodes (most connected - your core abstractions)
1. `Cheetah Market App Knowledge Base` - 12 edges
2. `main.py — FastAPI App + SSE + WebSocket Consumer` - 12 edges
3. `Dashboard.tsx — /dashboard Route` - 10 edges
4. `fetch_news()` - 6 edges
5. `cheetah_data.py — Data + Cheetah Score Engine` - 6 edges
6. `types.ts — TypeScript Interfaces` - 6 edges
7. `with_computed_scores()` - 5 edges
8. `Cheetah Score — 5-Factor Composite Formula` - 5 edges
9. `get_competitor_groups()` - 4 edges
10. `QuoteCache` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Cheetah Market App Knowledge Base` --references--> `main.py — FastAPI App + SSE + WebSocket Consumer`  [EXTRACTED]
  KNOWLEDGE_BASE.md → backend/main.py
- `main.py — FastAPI App + SSE + WebSocket Consumer` --implements--> `Server-Sent Events /stream Endpoint`  [EXTRACTED]
  backend/main.py → KNOWLEDGE_BASE.md
- `main.py — FastAPI App + SSE + WebSocket Consumer` --references--> `QuoteCache — In-Memory Rolling Window (64 ticks)`  [EXTRACTED]
  backend/main.py → KNOWLEDGE_BASE.md
- `Vite Dev Proxy (port 5173 → 8000)` --references--> `main.py — FastAPI App + SSE + WebSocket Consumer`  [EXTRACTED]
  KNOWLEDGE_BASE.md → backend/main.py
- `cheetah_data.py — Data + Cheetah Score Engine` --implements--> `Competitor Scout Groups (NVDA/CRDO peers)`  [EXTRACTED]
  backend/cheetah_data.py → KNOWLEDGE_BASE.md

## Communities

### Community 0 - "FastAPI Backend Core"
Cohesion: 0.14
Nodes (17): etfs(), finnhub_rest_poller(), finnhub_ws_consumer(), health(), lifespan(), QuoteCache, Market Stream — FastAPI Server-Sent Events backend.  Streams real-time quotes +, Rapidly-growing private unicorns (Tier 2 — not publicly tradable). (+9 more)

### Community 1 - "Data + Research Concepts"
Cohesion: 0.17
Nodes (17): cheetah_data.py — Data + Cheetah Score Engine, news.py — News Aggregation, FormulaCard.tsx — Cheetah Score Formula Display, IndicatorsCard.tsx — 12 Indicators + 8 Frameworks, 18 Tier 1 Cheetah Stocks, Caching Strategy, Cheetah Score — 5-Factor Composite Formula, Competitor Scout Groups (NVDA/CRDO peers) (+9 more)

### Community 2 - "Real-Time Streaming"
Cohesion: 0.14
Nodes (16): main.py — FastAPI App + SSE + WebSocket Consumer, QuoteRow.tsx — Per-Symbol Quote Display, Sparkline.tsx — Canvas Line Chart, QuoteCache — In-Memory Rolling Window (64 ticks), Real-Time Data Pipeline (Finnhub WebSocket → SSE → Frontend), Server-Sent Events /stream Endpoint, Vite Dev Proxy (port 5173 → 8000), App.tsx — Routes (+8 more)

### Community 3 - "Cheetah Score Engine"
Cohesion: 0.2
Nodes (11): compute_score(), get_competitor_groups(), Cheetah Score dataset — edit here to refresh the Dashboard page.  Each stock has, Apply FORMULA_WEIGHTS to the stock's bucket scores. Returns 0-100., Return copies of stocks with freshly computed `score` from buckets., Enrich each group with anchor metrics from CHEETAH_STOCKS., with_computed_scores(), cheetah() (+3 more)

### Community 4 - "News Aggregation"
Cohesion: 0.27
Nodes (11): news(), Aggregated real-time headlines from Finnhub + Yahoo RSS + Google News RSS., fetch_news(), _finnhub_news(), _google_news(), market_news(), _parse_rss(), Real-time news scraping for Cheetah tickers.  Uses three free sources, merged an (+3 more)

### Community 5 - "Dashboard Components"
Cohesion: 0.31
Nodes (10): CheetahTable.tsx — Sortable/Filterable Stock Table, CompetitorScoutCard.tsx — NVDA/CRDO Peer Comparison, EtfsCard.tsx — Thematic ETFs, NewsPanel.tsx — Aggregated Headlines, RefreshButton.tsx — Triggers /cheetah Recompute, UnicornsCard.tsx — Private Unicorn Proxies, types.ts — TypeScript Interfaces, useCheetahStocks.ts — Fetches /cheetah (+2 more)

### Community 6 - "Table Utilities"
Cohesion: 0.33
Nodes (0): 

### Community 7 - "ETF & Unicorn Cards"
Cohesion: 0.33
Nodes (3): EtfsCard(), UnicornsCard(), useJsonApi()

### Community 8 - "Dashboard Page + Hook"
Cohesion: 0.5
Nodes (2): Dashboard(), useCheetahStocks()

### Community 9 - "Refresh Button"
Cohesion: 0.67
Nodes (0): 

### Community 10 - "Quote Row Display"
Cohesion: 0.67
Nodes (0): 

### Community 11 - "News Panel"
Cohesion: 1.0
Nodes (2): NewsPanel(), relativeTime()

### Community 12 - "Live Stream Page"
Cohesion: 0.67
Nodes (0): 

### Community 13 - "App Router"
Cohesion: 1.0
Nodes (0): 

### Community 14 - "Navigation Bar"
Cohesion: 1.0
Nodes (0): 

### Community 15 - "Formula Card"
Cohesion: 1.0
Nodes (0): 

### Community 16 - "Sparkline Chart"
Cohesion: 1.0
Nodes (0): 

### Community 17 - "Indicators Card"
Cohesion: 1.0
Nodes (0): 

### Community 18 - "Market Stream Hook"
Cohesion: 1.0
Nodes (0): 

### Community 19 - "Vite Config"
Cohesion: 1.0
Nodes (0): 

### Community 20 - "App Entry Point"
Cohesion: 1.0
Nodes (0): 

### Community 21 - "TypeScript Types"
Cohesion: 1.0
Nodes (0): 

### Community 22 - "Competitor Scout Card"
Cohesion: 1.0
Nodes (0): 

### Community 23 - "Python Dependencies"
Cohesion: 1.0
Nodes (1): Backend Python Dependencies

### Community 24 - "Styles"
Cohesion: 1.0
Nodes (1): styles.css — Dark Theme

### Community 25 - "NavBar Component"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **29 isolated node(s):** `Cheetah Score dataset — edit here to refresh the Dashboard page.  Each stock has`, `Apply FORMULA_WEIGHTS to the stock's bucket scores. Returns 0-100.`, `Return copies of stocks with freshly computed `score` from buckets.`, `Enrich each group with anchor metrics from CHEETAH_STOCKS.`, `Market Stream — FastAPI Server-Sent Events backend.  Streams real-time quotes +` (+24 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `App Router`** (2 nodes): `App()`, `App.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Navigation Bar`** (2 nodes): `NavBar()`, `NavBar.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Formula Card`** (2 nodes): `FormulaCard()`, `FormulaCard.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Sparkline Chart`** (2 nodes): `Sparkline()`, `Sparkline.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Indicators Card`** (2 nodes): `IndicatorsCard()`, `IndicatorsCard.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Market Stream Hook`** (2 nodes): `useMarketStream()`, `useMarketStream.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Vite Config`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `App Entry Point`** (1 nodes): `main.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `TypeScript Types`** (1 nodes): `types.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Competitor Scout Card`** (1 nodes): `CompetitorScoutCard.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Python Dependencies`** (1 nodes): `Backend Python Dependencies`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Styles`** (1 nodes): `styles.css — Dark Theme`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `NavBar Component`** (1 nodes): `NavBar.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main.py — FastAPI App + SSE + WebSocket Consumer` connect `Real-Time Streaming` to `Data + Research Concepts`, `Dashboard Components`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `news()` connect `News Aggregation` to `FastAPI Backend Core`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `Dashboard.tsx — /dashboard Route` connect `Dashboard Components` to `Data + Research Concepts`, `Real-Time Streaming`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **What connects `Cheetah Score dataset — edit here to refresh the Dashboard page.  Each stock has`, `Apply FORMULA_WEIGHTS to the stock's bucket scores. Returns 0-100.`, `Return copies of stocks with freshly computed `score` from buckets.` to the rest of the system?**
  _29 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FastAPI Backend Core` be split into smaller, more focused modules?**
  _Cohesion score 0.14 - nodes in this community are weakly interconnected._
- **Should `Real-Time Streaming` be split into smaller, more focused modules?**
  _Cohesion score 0.14 - nodes in this community are weakly interconnected._