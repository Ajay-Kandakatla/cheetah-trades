# Ticker-details performance — measurement + fixes (2026-06-18)

_Ajay: "measure the app … ticker details too slow … optimize for low internet."_
The web-vitals RUM (`page_load_rum.md`) is the long-term passive collector; this
is the **active** measurement + the fixes it pointed to.

## What we measured

**Frontend (low-internet lens — shipped bytes):**

| chunk on the ticker-details page (gzipped) | before |
|---|---|
| `SepaCandidate` | 102 KB ← biggest in the app |
| `index` (entry, every page) | 79 KB |
| `SepaPoliticalChip` (shared card cluster) | 31 KB |
| ~240 KB gz total before interactive → **4–6 s on 3G** | |

**Backend — `GET /sepa/candidate/{symbol}`:** in-scan tickers are fast (served
from the persisted scan); **off-scan/searched tickers hit a ~7 s slow path**:

| step | time | waste |
|---|---|---|
| `rs_ranks` over all ~2,935 names | 5,061 ms | RS already stored per-symbol in the scan |
| `load_prices(force=True)` | 1,959 ms | cache returns the same data in 3 ms |
| `_analyze_symbol` | 39 ms | — |

## Fixes

**A — backend off-scan path (`rs_rank.rank_one` + cached prices).** Rank just the
searched symbol against a **per-scan-cached** universe-score distribution instead
of re-scoring the universe every request; use cached prices (cron keeps them
warm) instead of a forced refetch. **~7 s → ~5 s on the first off-scan hit per
scan cycle, <0.5 s after.** Same 1-99 percentile `rs_ranks` gives (locked by
`test_rs_rank_one.py`). In-scan symbols were already fast — untouched.

**B — frontend code-split.** Lazy-load the heavy, tab-gated / below-the-fold
components in `SepaCandidate` (DependencyGraph, StockAnalysisPanel, ChatterPanel,
GabbarLevels, RankTrendChart, TickerPatternPanel, ChartAnalysisPanel,
BreakoutHistoryBody, LiveCandlesChart) behind `Suspense`. **SepaCandidate chunk
337 → 125 KB raw (102 → 37 KB gz, −63 %).** Bonus: the candles chart's ~161 KB
charting lib now loads only when that chart is opened, not on every view.

**C — `SepaPoliticalChip` 95 KB: a measurement artifact, no change.** The chunk
contains no heavy library (verified: only component code + the tiny
`politicalDisclosures` data). vite merely *named* the shared **SepaCandidateCard
chip cluster** (41 imports) after the political chip. That card code is needed
immediately on the scan list, so deferring it would hurt that surface for no real
gain. The chip itself is tiny. The real adjacent win (the charting lib) was
captured by B.

## Verify / next

- `backend/tests/test_rs_rank_one.py` (rank_one == rs_ranks + per-scan cache).
- FE: full suite green (119); rebuild confirms the −63 % chunk drop.
- Once the **RUM is deployed** (`api frontend`), `GET /analytics/perf/summary`
  will show the LCP/INP drop on real ticker-details sessions — the closed loop.
- Follow-ups (not done): persist universe RS *scores* in the scan so even the
  first off-scan hit skips the ~5 s; trim the `index` entry chunk; add
  `rollup-plugin-visualizer` to chase shared-chunk composition precisely.
