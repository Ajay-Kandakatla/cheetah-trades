# Graph Report - .  (2026-04-25)

## Corpus Check
- Corpus is ~38,785 words - fits in a single context window. You may not need a graph.

## Summary
- 300 nodes · 346 edges · 44 communities detected
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 56 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0 rest|Community 0: rest]]
- [[_COMMUNITY_Community 1 stage|Community 1: stage]]
- [[_COMMUNITY_Community 2 sepa|Community 2: sepa]]
- [[_COMMUNITY_Community 3 cheetah|Community 3: cheetah]]
- [[_COMMUNITY_Community 4 market|Community 4: market]]
- [[_COMMUNITY_Community 5 base|Community 5: base]]
- [[_COMMUNITY_Community 6 news|Community 6: news]]
- [[_COMMUNITY_Community 7 fetch|Community 7: fetch]]
- [[_COMMUNITY_Community 8 indian|Community 8: indian]]
- [[_COMMUNITY_Community 9 mon-fri|Community 9: mon-fri]]
- [[_COMMUNITY_Community 10 usesepa.ts|Community 10: usesepa.ts]]
- [[_COMMUNITY_Community 11 usetheme.ts|Community 11: usetheme.ts]]
- [[_COMMUNITY_Community 12 vcp.py|Community 12: vcp.py]]
- [[_COMMUNITY_Community 13 trend|Community 13: trend]]
- [[_COMMUNITY_Community 14 indianstocktable.tsx|Community 14: indianstocktable.tsx]]
- [[_COMMUNITY_Community 15 quoterow.tsx|Community 15: quoterow.tsx]]
- [[_COMMUNITY_Community 16 frontendindex.html|Community 16: frontend/index.html]]
- [[_COMMUNITY_Community 17 enhancedindianstocktable()|Community 17: enhancedindianstocktable()]]
- [[_COMMUNITY_Community 18 useindianstocks.ts|Community 18: useindianstocks.ts]]
- [[_COMMUNITY_Community 19 indianmarketindices.tsx|Community 19: indianmarketindices.tsx]]
- [[_COMMUNITY_Community 20 watchlistsection.tsx|Community 20: watchlistsection.tsx]]
- [[_COMMUNITY_Community 21 indiannewspanel.tsx|Community 21: indiannewspanel.tsx]]
- [[_COMMUNITY_Community 22 app()|Community 22: app()]]
- [[_COMMUNITY_Community 23 navbar.tsx|Community 23: navbar.tsx]]
- [[_COMMUNITY_Community 24 sparkline.tsx|Community 24: sparkline.tsx]]
- [[_COMMUNITY_Community 25 stockdetailmodal.tsx|Community 25: stockdetailmodal.tsx]]
- [[_COMMUNITY_Community 26 livestream.tsx|Community 26: livestream.tsx]]
- [[_COMMUNITY_Community 27 moderndashboard.tsx|Community 27: moderndashboard.tsx]]
- [[_COMMUNITY_Community 28 stream|Community 28: /stream]]
- [[_COMMUNITY_Community 29 vite.config.ts|Community 29: vite.config.ts]]
- [[_COMMUNITY_Community 30 main.tsx|Community 30: main.tsx]]
- [[_COMMUNITY_Community 31 types.ts|Community 31: types.ts]]
- [[_COMMUNITY_Community 32 sepacandidatemodal.tsx|Community 32: sepacandidatemodal.tsx]]
- [[_COMMUNITY_Community 33 sepabriefbanner.tsx|Community 33: sepabriefbanner.tsx]]
- [[_COMMUNITY_Community 34 themetoggle.tsx|Community 34: themetoggle.tsx]]
- [[_COMMUNITY_Community 35 watchlist.ts|Community 35: watchlist.ts]]
- [[_COMMUNITY_Community 36 sepa.tsx|Community 36: sepa.tsx]]
- [[_COMMUNITY_Community 37 vite|Community 37: vite]]
- [[_COMMUNITY_Community 38 backend|Community 38: backend]]
- [[_COMMUNITY_Community 39 fastapi|Community 39: fastapi]]
- [[_COMMUNITY_Community 40 uvicorn|Community 40: uvicorn]]
- [[_COMMUNITY_Community 41 httpx|Community 41: httpx]]
- [[_COMMUNITY_Community 42 websockets|Community 42: websockets]]
- [[_COMMUNITY_Community 43 python-dotenv|Community 43: python-dotenv]]

## God Nodes (most connected - your core abstractions)
1. `Cheetah Market App Knowledge Base` - 10 edges
2. `SEPA (Specific Entry Point Analysis)` - 10 edges
3. `Dashboard.tsx — /dashboard Route` - 9 edges
4. `_analyze_symbol()` - 9 edges
5. `load_prices()` - 9 edges
6. `fetch_indian_market()` - 6 edges
7. `fetch_news()` - 6 edges
8. `market_state()` - 6 edges
9. `scan_universe()` - 6 edges
10. `generate_brief()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `FormulaCard.tsx — Cheetah Score Formula Display` --references--> `Cheetah Score — 5-Factor Composite Formula`  [EXTRACTED]
  frontend/src/components/FormulaCard.tsx → KNOWLEDGE_BASE.md
- `cheetah_data.py — Data + Cheetah Score Engine` --implements--> `18 Tier 1 Cheetah Stocks`  [EXTRACTED]
  backend/cheetah_data.py → KNOWLEDGE_BASE.md
- `cheetah_data.py — Data + Cheetah Score Engine` --implements--> `Private Unicorns with Public Proxies (12 companies)`  [EXTRACTED]
  backend/cheetah_data.py → KNOWLEDGE_BASE.md
- `cheetah_data.py — Data + Cheetah Score Engine` --implements--> `Competitor Scout Groups (NVDA/CRDO peers)`  [EXTRACTED]
  backend/cheetah_data.py → KNOWLEDGE_BASE.md
- `IndicatorsCard.tsx — 12 Indicators + 8 Frameworks` --references--> `Expert Frameworks (O'Neil, Greenblatt, Piotroski, Lynch, Minervini, Buffett, Graham, Weinstein)`  [EXTRACTED]
  frontend/src/components/IndicatorsCard.tsx → KNOWLEDGE_BASE.md

## Hyperedges (group relationships)
- **SEPA core pillars** — minervini_trend_template, minervini_vcp, minervini_power_play, minervini_rs_rank, minervini_risk_rules [INFERRED 0.85]
- **Four-stage market cycle** — minervini_stage_1, minervini_stage_2, minervini_stage_3, minervini_stage_4 [EXTRACTED 1.00]
- **Cheetah launchd SEPA pipeline** — readme_scan_plist, readme_brief_plist, readme_latest_json, readme_brief_json, readme_sepa_cli [EXTRACTED 1.00]

## Communities

### Community 0 - "Community 0: rest"
Cohesion: 0.08
Nodes (30): cheetah(), competitors(), etfs(), finnhub_rest_poller(), finnhub_ws_consumer(), health(), lifespan(), QuoteCache (+22 more)

### Community 1 - "Community 1: stage"
Cohesion: 0.07
Nodes (28): backend/sepa/base_count.py, backend/sepa/market_context.py, Base Count (1st, 2nd, 3rd stage bases), 4 Stages of a Stock, Leadership stocks in strong groups, Market Context / General Market Health, Trade Like a Stock Market Wizard (Minervini), Pivot Point Buy (+20 more)

### Community 2 - "Community 2: sepa"
Cohesion: 0.1
Nodes (23): generate_brief(), load_brief(), Morning brief — "what to watch when I open the app at 8:30am".  Consumes the 5pm, _watchlist_status(), Minervini SEPA — screener, morning brief, catalyst + insider signals., _fts_search(), insider_activity(), Insider & institutional activity via SEC EDGAR (free, no key).  Three signals: (+15 more)

### Community 3 - "Community 3: cheetah"
Cohesion: 0.1
Nodes (26): cheetah_data.py — Data + Cheetah Score Engine, CheetahTable.tsx — Sortable/Filterable Stock Table, CompetitorScoutCard.tsx — NVDA/CRDO Peer Comparison, EtfsCard.tsx — Thematic ETFs, FormulaCard.tsx — Cheetah Score Formula Display, IndicatorsCard.tsx — 12 Indicators + 8 Frameworks, NewsPanel.tsx — Aggregated Headlines, RefreshButton.tsx — Triggers /cheetah Recompute (+18 more)

### Community 4 - "Community 4: market"
Cohesion: 0.11
Nodes (19): main(), SEPA command-line entrypoints — invoked by launchd cron jobs.  Usage:     python, age(), IPO-age filter — young companies preferred (Ch 11).  "80% of 1990s winners were, market_state(), Market context gate.  Book Ch 13: ">90% of superperformance begins coming out of, _cache_path(), load_prices() (+11 more)

### Community 5 - "Community 5: base"
Cohesion: 0.1
Nodes (15): count_bases(), Base count — which base # is the stock in (1=primary, 2, 3, ...).  Book Ch 11: e, sepa_position_plan(), detect(), Power Play setup detector — Minervini Ch 10 p.254-255.  Criteria:   1. Explosive, plan_position(), PositionPlan, Position sizing + stop placement — Minervini risk rules (Ch 12-13).  Key numbers (+7 more)

### Community 6 - "Community 6: news"
Cohesion: 0.19
Nodes (15): indian_news_endpoint(), news(), Aggregated real-time headlines from Finnhub + Yahoo RSS + Google News RSS., Indian market news from Google News RSS (India edition).      Pass ?symbol=RELIA, fetch_news(), _finnhub_news(), _google_news(), indian_news() (+7 more)

### Community 7 - "Community 7: fetch"
Cohesion: 0.21
Nodes (10): catalyst_for(), _fetch_finnhub_earnings(), _fetch_google_news(), _fetch_yfinance_extras(), Catalyst detection — what could move a SEPA candidate today.  Three inputs:   1., Synchronous — run in a thread via asyncio., Use Google News RSS — no key required., _score_headline() (+2 more)

### Community 8 - "Community 8: indian"
Cohesion: 0.27
Nodes (9): _build_index(), _build_stock(), fetch_indian_market(), _fetch_yahoo_chart(), Real-time Indian market data from Yahoo Finance (free, no API key).  Uses Yahoo', Fetch all stocks + indices in parallel with a short-lived cache., Hit Yahoo's free chart endpoint. Returns the `meta` object or None., indian_stocks() (+1 more)

### Community 9 - "Community 9: mon-fri"
Cohesion: 0.24
Nodes (10): ~/.cheetah/scans/brief.json, com.cheetah.sepa.brief.plist, Mon-Fri 8:30am morning brief, ~/.cheetah/scans/latest.json, launchctl load/unload/start, launchd/README.md, Polygon API integration, com.cheetah.sepa.scan.plist (+2 more)

### Community 10 - "Community 10: usesepa.ts"
Cohesion: 0.22
Nodes (0): 

### Community 11 - "Community 11: usetheme.ts"
Cohesion: 0.47
Nodes (3): readStoredTheme(), resolveInitial(), systemPrefersDark()

### Community 12 - "Community 12: vcp.py"
Cohesion: 0.4
Nodes (5): detect(), _find_swings(), VCP — Volatility Contraction Pattern detector.  Book Ch 10 (p.198-213):   - Base, Return [(idx, price, 'H'|'L'), ...] using simple local-extrema rule., Detect a VCP in the last `lookback_days` bars. Returns None if no     discernibl

### Community 13 - "Community 13: trend"
Cohesion: 0.4
Nodes (4): evaluate(), Minervini Trend Template — the 8 Stage-2 criteria.  A stock must satisfy ALL eig, Run all 8 checks against a daily OHLCV frame. Needs ~252 trading days., TrendResult

### Community 14 - "Community 14: indianstocktable.tsx"
Cohesion: 0.4
Nodes (0): 

### Community 15 - "Community 15: quoterow.tsx"
Cohesion: 0.4
Nodes (0): 

### Community 16 - "Community 16: frontend/index.html"
Cohesion: 0.5
Nodes (5): frontend/index.html, Google Fonts (Fraunces, Geist, JetBrains Mono), /src/main.tsx entry, #root mount node, Cheetah Market - Live + Dashboard

### Community 17 - "Community 17: enhancedindianstocktable()"
Cohesion: 0.5
Nodes (0): 

### Community 18 - "Community 18: useindianstocks.ts"
Cohesion: 0.5
Nodes (2): IndianMarket(), useIndianStocks()

### Community 19 - "Community 19: indianmarketindices.tsx"
Cohesion: 0.67
Nodes (0): 

### Community 20 - "Community 20: watchlistsection.tsx"
Cohesion: 0.67
Nodes (0): 

### Community 21 - "Community 21: indiannewspanel.tsx"
Cohesion: 1.0
Nodes (2): IndianNewsPanel(), relativeTime()

### Community 22 - "Community 22: app()"
Cohesion: 1.0
Nodes (0): 

### Community 23 - "Community 23: navbar.tsx"
Cohesion: 1.0
Nodes (0): 

### Community 24 - "Community 24: sparkline.tsx"
Cohesion: 1.0
Nodes (0): 

### Community 25 - "Community 25: stockdetailmodal.tsx"
Cohesion: 1.0
Nodes (0): 

### Community 26 - "Community 26: livestream.tsx"
Cohesion: 1.0
Nodes (0): 

### Community 27 - "Community 27: moderndashboard.tsx"
Cohesion: 1.0
Nodes (0): 

### Community 28 - "Community 28: /stream"
Cohesion: 1.0
Nodes (2): Server-Sent Events /stream Endpoint, useMarketStream.ts — EventSource to /stream

### Community 29 - "Community 29: vite.config.ts"
Cohesion: 1.0
Nodes (0): 

### Community 30 - "Community 30: main.tsx"
Cohesion: 1.0
Nodes (0): 

### Community 31 - "Community 31: types.ts"
Cohesion: 1.0
Nodes (0): 

### Community 32 - "Community 32: sepacandidatemodal.tsx"
Cohesion: 1.0
Nodes (0): 

### Community 33 - "Community 33: sepabriefbanner.tsx"
Cohesion: 1.0
Nodes (0): 

### Community 34 - "Community 34: themetoggle.tsx"
Cohesion: 1.0
Nodes (0): 

### Community 35 - "Community 35: watchlist.ts"
Cohesion: 1.0
Nodes (0): 

### Community 36 - "Community 36: sepa.tsx"
Cohesion: 1.0
Nodes (0): 

### Community 37 - "Community 37: vite"
Cohesion: 1.0
Nodes (1): Vite Dev Proxy (port 5173 → 8000)

### Community 38 - "Community 38: backend"
Cohesion: 1.0
Nodes (1): Backend Python Dependencies

### Community 39 - "Community 39: fastapi"
Cohesion: 1.0
Nodes (1): FastAPI 0.115.4

### Community 40 - "Community 40: uvicorn"
Cohesion: 1.0
Nodes (1): Uvicorn 0.32.0

### Community 41 - "Community 41: httpx"
Cohesion: 1.0
Nodes (1): HTTPX 0.27.2

### Community 42 - "Community 42: websockets"
Cohesion: 1.0
Nodes (1): WebSockets 13.1

### Community 43 - "Community 43: python-dotenv"
Cohesion: 1.0
Nodes (1): Python-dotenv 1.0.1

## Knowledge Gaps
- **95 isolated node(s):** `CheetahTable.tsx — Sortable/Filterable Stock Table`, `NewsPanel.tsx — Aggregated Headlines`, `CompetitorScoutCard.tsx — NVDA/CRDO Peer Comparison`, `EtfsCard.tsx — Thematic ETFs`, `UnicornsCard.tsx — Private Unicorn Proxies` (+90 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 22: app()`** (2 nodes): `App()`, `App.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23: navbar.tsx`** (2 nodes): `NavBar.tsx`, `NavBar()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24: sparkline.tsx`** (2 nodes): `Sparkline.tsx`, `Sparkline()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25: stockdetailmodal.tsx`** (2 nodes): `StockDetailModal.tsx`, `onKey()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26: livestream.tsx`** (2 nodes): `LiveStream.tsx`, `LiveStream()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27: moderndashboard.tsx`** (2 nodes): `ModernDashboard.tsx`, `ModernDashboard()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28: /stream`** (2 nodes): `Server-Sent Events /stream Endpoint`, `useMarketStream.ts — EventSource to /stream`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29: vite.config.ts`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30: main.tsx`** (1 nodes): `main.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31: types.ts`** (1 nodes): `types.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32: sepacandidatemodal.tsx`** (1 nodes): `SepaCandidateModal.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33: sepabriefbanner.tsx`** (1 nodes): `SepaBriefBanner.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34: themetoggle.tsx`** (1 nodes): `ThemeToggle.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35: watchlist.ts`** (1 nodes): `watchlist.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36: sepa.tsx`** (1 nodes): `Sepa.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37: vite`** (1 nodes): `Vite Dev Proxy (port 5173 → 8000)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38: backend`** (1 nodes): `Backend Python Dependencies`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39: fastapi`** (1 nodes): `FastAPI 0.115.4`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40: uvicorn`** (1 nodes): `Uvicorn 0.32.0`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41: httpx`** (1 nodes): `HTTPX 0.27.2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42: websockets`** (1 nodes): `WebSockets 13.1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43: python-dotenv`** (1 nodes): `Python-dotenv 1.0.1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_analyze_symbol()` connect `Community 5: base` to `Community 2: sepa`, `Community 4: market`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `sepa_position_plan()` connect `Community 5: base` to `Community 0: rest`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `load_latest()` connect `Community 2: sepa` to `Community 4: market`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `_analyze_symbol()` (e.g. with `load_prices()` and `evaluate()`) actually correct?**
  _`_analyze_symbol()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `load_prices()` (e.g. with `market_state()` and `_analyze_symbol()`) actually correct?**
  _`load_prices()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `CheetahTable.tsx — Sortable/Filterable Stock Table`, `NewsPanel.tsx — Aggregated Headlines`, `CompetitorScoutCard.tsx — NVDA/CRDO Peer Comparison` to the rest of the system?**
  _95 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0: rest` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._