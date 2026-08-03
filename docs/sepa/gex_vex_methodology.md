# GEX Board + VEX + Best-Case Lens — `backend/options/opex.py` / `gex_history.py`

Shipped 2026-07-17 (Ajay: "build me a Gamma exposure page … bullish stocks
with key nodes and bearish stocks" + "add VEX and GEX to individual stocks to
show me the best case possibility in the setup tab").

**Source honesty (this is NOT Minervini):** dealer-positioning analytics are
industry heuristics (SqueezeMetrics / SpotGamma lineage), not book-cited
methodology. Nothing here feeds the scanner's gates, the score, `is_buyable`,
or Auto-Pilot — same hard boundary as the orderflow page. It colors the SEPA
setup; it never overrides it.

## Definitions (and the sign rule)

- **GEX** — per strike: `±gamma × OI × 100 × 0.01 × spot²` ($ of dealer
  hedging per 1% move). Sign rule: calls **+**, puts **−** (dealer long
  call-gamma / short put-gamma — the blind heuristic; can invert on
  single-name momentum leaders, hence the per-row reliability badge:
  `index` vs `single_name`).
- **Flip (zero-gamma)** — walk strikes ascending, accumulate per-strike net
  gamma; the flip is the interpolated crossing where the running sum changes
  sign. Above it dealers dampen moves, below it they amplify. One-sided
  profiles have **no flip** (`None`) — the regime field carries the read.
- **Walls / magnet** — largest +gamma strike at/above spot (call wall),
  largest −gamma strike at/below (put wall), largest |gamma| node (magnet).
  Range brackets and gravity, **not price targets**.
- **VEX** — **net dealer VANNA** (∂Delta/∂IV), scale `100 × 0.01 × spot` ($
  dealer delta per 1 vol-pt). NAMING HONESTY: retail tools disagree — some
  call vega exposure "VEX"; we use the vanna meaning (GEXBot/SpotGamma
  style) because it has the tradeable mechanic: **net vanna positive →
  falling IV forces dealer BUYING** ("vanna tailwind"), negative → falling
  IV forces selling. Vanna is never in the Massive snapshot — always
  Black-Scholes-derived from IV (`_bs_vanna`, r≈0), one modelling step
  further from the tape than GEX. Same blind call=+/put=− dealer rule.

## The board (`/gex-board`, GET /options/gex-board)

Rows come from the nightly **17:50 ET cron** (`options.gex_history`, ~200
names: portfolio + watchlists + SOIR bullish/watch + top SEPA; POST
/options/gex-board/refresh re-sweeps on demand, threaded ×8). Bucketing is
BACKEND logic (`gex_history.board_bucket`, unit-tested) so page and engine
can't drift:

| bucket | rule |
|---|---|
| 🟢 bullish | regime `pinning` AND spot ≥ flip (or no flip) |
| 🔴 bearish | regime `amplifying` AND spot < flip (or no flip) |
| 🌫️ mixed | regime and flip disagree — shown collapsed, weakest claim |

Buckets sort by \|net GEX\| descending. Ledger rows written before
2026-07-17 lack `flip_strike`/VEX → bucketed on regime alone (the board
notes how many, self-heals on the next snapshot).

## The Setup-tab lens (`GexSetupLens`, /options/opex/{sym})

`opex.best_case(spot, gamma, vex)` (pure, unit-tested) renders the
plain-English read: bias (gamma helps / hurts / split), the best-case path
(grind to call wall / reclaim the flip), the risk line (losing the flip /
put wall), and the vanna note. It derives ONLY from computed levels — never
invents prices. No chain → renders nothing (Setup tab stays clean).

## Tests

`tests/test_opex.py` (flip interpolation + one-sided None, top-node
ordering, vanna signs + degenerate inputs, VEX reads + fail-closed,
best-case buckets + None guards) and `tests/test_soir_coverage_gex.py`
(slim_row None-safe new fields, board_bucket table, board latest-date
selection/sorting/notes). FE: `lib/gexBoard.test.ts`.
