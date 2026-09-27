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

## Chart Maps 🧲 chip + coverage (2026-09-27)

Full write-up: `docs/chart_maps/gex_chips_2026_09_27.md`. What changed for this ledger:

- **Coverage grew.** The 17:50 ET sweep (`run()`, cron default `include_chart_maps=True`) now also covers every name
  a Chart Maps tab served in the last `NIGHTLY_MAX_AGE_DAYS` (7), at most `chart_maps.board.LIMIT_MAX` (80) per tab
  (Mongo `chart_maps_seen`, `chart_maps.gex_seen`). That is about 175 → 800+ names, and the sweep takes about
  2–3.5 min at `SWEEP_WORKERS` (8). The core universe is unchanged and still capped at `MAX_UNIVERSE` 200.
- **Rows are tagged** `universe: "core" | "chart_maps"`. The GEX Board page shows both (H10).
- **The refresh button stays core-only.** `POST /options/gex-board/refresh` calls `run(include_chart_maps=False)`
  because it runs behind a request.
- **Index.** `{symbol: 1, date_et: -1}` (`symbol_date`) via `ensure_index()`, in `run()` and once per process in
  `snapshot_for`.
- **Settled rows are still stored and still read here.** A row whose nearest expiry had settled when it was
  recorded is shown as "no read" on Chart Maps only (`chart_maps.gex_read.settled`). The GEX Board, the push context
  line (`supply_demand.bullish_context`) and the Desk report read them unchanged. The engine fix (skip a settled
  expiry inside `compute_opex`) is his call (H19).
- The Chart Maps live read is never written to this ledger.
- Still **not Minervini**, still never an input to scanner gates, the score, `is_buyable`, alerts or Auto-Pilot.
