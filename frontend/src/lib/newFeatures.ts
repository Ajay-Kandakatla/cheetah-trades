/* newFeatures — registry of recently-shipped features.
 *
 * Ajay 2026-06-18: "whenever we push a new feature, add a visual highlight, and
 * until I view it for the first time log it to analytics."
 *
 * HOW TO USE WHEN YOU SHIP A FEATURE: add one entry below. It then shows a ✨ NEW
 * highlight (nav badge for `route`, and/or an in-place <NewBadge id="..."/>) until
 * the user first views it; impressions + the first view are logged to analytics
 * (see useNewFeatures + /features/* endpoints). Entries older than
 * NEW_WINDOW_DAYS stop highlighting automatically — leave them or prune.
 */
export type NewFeature = {
  /** Stable unique id — also the analytics key. Kebab-case. */
  id: string;
  /** Human label for the what's-new list / tooltip. */
  label: string;
  /** ISO date (YYYY-MM-DD) the feature shipped. */
  addedAt: string;
  /** Page the feature lives on. Visiting it clears the highlight. Omit for
   *  features not tied to a single route (cleared via <NewBadge> interaction). */
  route?: string;
};

export const NEW_FEATURES: NewFeature[] = [
  { id: 'breakouts',            label: 'Breakouts page',                      addedAt: '2026-06-16', route: '/breakouts' },
  { id: 'breakouts-columns',    label: 'Column guide on the Breakouts table', addedAt: '2026-06-17', route: '/breakouts' },
  { id: 'breakouts-beta',       label: 'Beta column + sort by low volatility', addedAt: '2026-06-17', route: '/breakouts' },
  { id: 'market-gauge-events',  label: 'FOMC & macro events on Market Gauge',  addedAt: '2026-06-17', route: '/market-gauge' },
  { id: 'page-load-monitoring', label: 'Page-load speed monitoring',           addedAt: '2026-06-18' },
  { id: 'breakouts-dynamic-scan', label: 'Update button — fast re-scan on Breakouts', addedAt: '2026-06-18', route: '/breakouts' },
  { id: 'autopilot-pnl-summary', label: 'Auto-Pilot account P&L — made/lost money since start', addedAt: '2026-06-18', route: '/trading' },
  { id: 'mvp-indicator', label: 'MVP indicator — runner vs late-stage exhaustion (Champion book)', addedAt: '2026-06-19', route: '/sepa' },
  { id: 'breakouts-buyable', label: '🎯 Buyable filter + badge on the Breakouts page', addedAt: '2026-06-19', route: '/breakouts' },
  { id: 'breakout-footprint', label: "Breakout chart: who's behind each breakout (institutional vs churn) + emerging setups", addedAt: '2026-06-21', route: '/sepa' },
  { id: 'climax-distribution', label: 'Climax-top distribution: when institutions are selling the run into retail buying', addedAt: '2026-06-21', route: '/sepa' },
  { id: 'distribution-blocks-enter', label: 'Distribution now blocks Enter — names institutions are selling are held out of the buy tier', addedAt: '2026-06-21', route: '/sepa' },
  { id: 'conviction-rank', label: '🏆 Conviction rank — lists now sort by return potential (volume + dried volume + momentum); climax runs sink', addedAt: '2026-06-22', route: '/sepa' },
  { id: 'conviction-rank-breakouts', label: '🏆 Conviction column + sort on the Breakouts board', addedAt: '2026-06-22', route: '/breakouts' },
  { id: 'cheat-tag', label: '🃏 Cheat tag — the earliest entry (TTLAC), shown in a red market when there are no breakouts', addedAt: '2026-06-22', route: '/sepa' },
  { id: 'breakouts-fresh-only', label: '🌱 Fresh only — hide extended (→R2/Past R2) names, keep the board to fresh breakouts', addedAt: '2026-06-23', route: '/breakouts' },
  { id: 'sepa-global', label: '🌍 SEPA Global — a simple, beginner-friendly version of the scanner (same Minervini rules)', addedAt: '2026-06-23', route: '/sepa-global' },
  { id: 'leveraged-badge', label: '⚠️ Leveraged-ETF flag (2x/3x) now shows on every list — they’re not Minervini stock setups', addedAt: '2026-06-23', route: '/sepa' },
  { id: 'tomorrow-bias-options', label: '🌙 Tomorrow bias — overnight/after-hours + options flow → a next-open lean on every ticker’s options-flow tab', addedAt: '2026-06-26', route: '/sepa' },
  { id: 'market-tomorrow-bias', label: '🌙 Market Tomorrow Bias — SPY/QQQ overnight gap + VIX + regime → one lean for the next session', addedAt: '2026-06-26', route: '/overnight' },
  { id: 'options-net-direction', label: '📈 Bull/Bear stock tag on the options-flow tab — plain direction next to the contrarian SOIR signal', addedAt: '2026-06-26', route: '/sepa' },
  { id: 'autopilot-analysis-column', label: '🐆 Analysis column on Auto-Pilot — the Cheetah Verdict (Minervini + Bonde) on every engine position', addedAt: '2026-06-26', route: '/trading' },
  { id: 'portfolio-buy-verdict', label: '🐆 Buy verdict on each Portfolio holding — the ENTER/WATCH/AVOID read + criteria, at a glance', addedAt: '2026-06-26', route: '/portfolio' },
  { id: 'autopilot-pnl-simple', label: '💰 Simpler Auto-Pilot P&L — started vs now total (what we gained together), realized/unrealized in the tooltip', addedAt: '2026-06-26', route: '/trading' },
  { id: 'opex-gamma-panel', label: '🧲 OpEx panel — next expiration + max-pain magnet + dealer-gamma (pin vs amplify) on the options-flow tab', addedAt: '2026-06-26', route: '/sepa' },
  { id: 'tape-order-flow', label: '🧾 Tape tab — order flow on every ticker: delta, big prints, trade flashes, volume profile + a deterministic BUY/WAIT/AVOID checklist with its own measured track record', addedAt: '2026-07-06', route: '/sepa' },
  { id: 'learning-path', label: '📚 Learning Path — your phased study plan (order flow → SMC → options vol → synthesis) with embedded videos + papers', addedAt: '2026-07-06', route: '/learning' },
  { id: 'autopilot-position-totals', label: '💵 Cost / Now / ± columns on Auto-Pilot positions + a TOTAL row summing the pluses and minuses + cash not entered', addedAt: '2026-07-06', route: '/trading' },
  { id: 'breakout-breadth', label: '🌡️ Breakout Breadth strip — breakouts/day + follow-through vs failure rate + the book\'s exposure read (sizes positions, never gates entries)', addedAt: '2026-07-10', route: '/breakouts' },
  { id: 'autopilot-rules-rs-floor', label: '📜 Auto-Pilot rules ⓘ — every rule the engine enforces, served by the engine itself; plus a new RS ≥ 80 floor (p.79 "80s or 90s") and a scan-trust gate (fresh + market-sized scans only)', addedAt: '2026-07-12', route: '/trading' },
  { id: 'autopilot-pilot-and-leaky-pivot', label: '🛫 Pilot-size entries (half size until the last 5 trades prove out, per Minervini\'s progressive exposure) + leaky-pivot suppressor (skip pivots that keep poking above and failing)', addedAt: '2026-07-12', route: '/trading' },
  { id: 'sepa-leaky-pivot', label: '🚱 Leaky pivots on the scanner — SEPA Global moves them from "Buy now" to Watch, and SEPA cards flag them, using the exact rule Auto-Pilot enforces', addedAt: '2026-07-12', route: '/sepa' },
  { id: 'autopilot-pyramiding', label: '🏗️ Pyramid adds — Auto-Pilot tops a winning position up to full size when it sets up again at a higher pivot (TTLAC "Add and Reduce"); violet auto_pyramid rows in the ledger', addedAt: '2026-07-12', route: '/trading' },
  { id: 'gex-board', label: '🧲 GEX Board — bullish vs bearish stocks by dealer gamma, each with its key nodes (flip, call/put walls, magnet) + net GEX/VEX off the options key', addedAt: '2026-07-17', route: '/gex-board' },
  { id: 'gex-setup-lens', label: '🎯 Options lens on the Setup tab — GEX + VEX best-case read per stock (does dealer hedging help or fight this setup?)', addedAt: '2026-07-17', route: '/sepa' },
  { id: 'breakouts-sort-vcp-churn', label: '🚀 Breakouts: Sort dropdown (volume options lead), 📐 VCP/setup badges on every row, and spike-and-dump days no longer count as breakouts (the GSAT fix)', addedAt: '2026-08-03', route: '/breakouts' },
  { id: 'demand-reentry-scan', label: '🟢 Back in Demand — scan the S&P 500 for names that pulled back INTO a demand zone they had left (with a Scan button), each with buy band / stop / target', addedAt: '2026-08-13', route: '/supply-demand' },
  { id: 'zone-map-setup-tab', label: '📉 Supply/demand zones drawn on every stock — red supply, green demand, with BUY band, STOP and TARGET written on the chart (Setup tab)', addedAt: '2026-08-13', route: '/sepa' },
  { id: 'quote-rule-delta', label: '🎯 Delta now classified against the real NBBO quote (Lee-Ready), not the tick-rule estimate — on CIEN the old way understated net selling by 2× (Tape tab)', addedAt: '2026-08-13', route: '/sepa' },
  { id: 'zone-map-dark-blocks', label: '🟣 Off-exchange blocks on the zone chart — every large dark print plotted at its price, flagged when it landed inside your buy band', addedAt: '2026-08-13', route: '/sepa' },
  { id: 'retail-flow', label: '🧍 Retail flow — which side retail is on, identified by sub-penny off-exchange prints and signed on the quote midpoint; ⚡ flags retail leaning against the block money', addedAt: '2026-08-14', route: '/supply-demand' },
  { id: 'sd-rr-sort-liquidity', label: '📊 Back in Demand sorted by R:R, with the win rate you\'d need to break even, daily $ volume + liquidity tier, and a dark-pool rating on every top row', addedAt: '2026-08-13', route: '/supply-demand' },
  { id: 'sd-universe-sp1500', label: '🌐 Back in Demand now scans beyond the S&P 500 — pick S&P 1500 to add ~1,000 MidCap + SmallCap names (index-quality, not a raw Russell slice)', addedAt: '2026-08-13', route: '/supply-demand' },
  { id: 'sd-knife-guard', label: '🔪 Back in Demand now filters falling knives (swing lows stepping down + falling 50-day) instead of the Minervini template — CIEN/VRT/CAT dropped off', addedAt: '2026-08-13', route: '/supply-demand' },
  { id: 'dark-pool-prints', label: '🟣 Where it printed — lit vs off-exchange (dark pool) volume split + the largest off-exchange blocks, on every ticker\'s Tape tab', addedAt: '2026-08-13', route: '/sepa' },
  { id: 'chart-maps', label: '🗺️ Chart Maps — a charts-only study board: strong VCP bases, pullbacks back into demand, and past setups from your own ledger that hit target before their stop. Every chart clicks through to the ticker.', addedAt: '2026-08-15', route: '/chart-maps' },
  { id: 'rotation-tracker', label: 'Sector Rotation — where money left and went, vs equal-weight', addedAt: '2026-08-16', route: '/rotation' },
  { id: 'zone-winners', label: '🏆 Past Winners now has a Demand zones source — 5 years of backtested zone re-entries', addedAt: '2026-08-16', route: '/chart-maps' },
  { id: 'demand-rr-floor', label: '🎯 R:R floor on Back in Demand — 36% of this board\'s backtested wins hit target on the ENTRY bar at a median 0.45R; the floor (default 1.0, adjustable, 0 = off) removes those and says how many it dropped', addedAt: '2026-08-17', route: '/supply-demand' },
  { id: 'zone-chart-fullscreen', label: '⤢ Expand the zone chart to full screen — on names like SNDK the bands sat a few pixels apart in a 340px pane; the expand button (or Esc to close) gives them the whole viewport', addedAt: '2026-08-17', route: '/sepa' },
  { id: 'chart-maps-declutter', label: '🧹 Chart Maps dropdown cleaned up — "$ turnover" is gone (it was today\'s DOLLARS, not average volume), the two volume sorts now say their unit, and AI-sector names no longer lead by default (the Themes first checkbox still does it)', addedAt: '2026-08-17', route: '/chart-maps' },
  { id: 'demand-scan-progress', label: '🔎 Live scan progress on Back in Demand — real ticker-by-ticker count, hits as they are found and an ETA, on both the Supply/Demand tab and Chart Maps (they watch the same scan)', addedAt: '2026-08-17', route: '/supply-demand' },
  { id: 'broken-band-guard', label: '🚫 A demand zone that BROKE is no longer a buy — a close below the floor drops the name (8 of 17 S&P 500 rows came off, SWKS was 18% under its band), the chart says BROKEN instead of BUY, and a stop the market already ran gets flagged', addedAt: '2026-08-17', route: '/supply-demand' },
  { id: 'chart-window', label: 'Chart window control (6m / 9m / 1y) + demand-zone charts now reach back to the touches that made the zone', addedAt: '2026-08-16', route: '/chart-maps' },
  { id: 'themes-power-energy', label: 'New rosters: AI power (IREN, CRWV) + energy, with space/quantum/semis priority', addedAt: '2026-08-16', route: '/chart-maps' },
  { id: 'chart-maps-themes', label: '⚛ Quantum / nuclear / robotics / AI-semis names now scanned — IONQ, OKLO, SMR, ARM, ALAB, CRDO and 15 more that the S&P indices structurally cannot hold', addedAt: '2026-08-15', route: '/chart-maps' },
  { id: 'chart-maps-sort-progress', label: '📊 Chart Maps: sort by retail imbalance, retail %, off-exchange %, relative volume, $ turnover, conviction or RS — ranked across the whole scan, not just the tiles on screen — plus a liquidity floor (default $10M/day, so thin names stop teaching you untradeable bases), live ticker scan progress and a Re-scan button', addedAt: '2026-08-17', route: '/chart-maps' },
  { id: 'zone-chart-candles', label: '🕯️ Zone chart rebuilt — real candlesticks + volume, and hover any day for its open / high / low / close / % change / volume. Zones now track zoom and pan (Setup tab)', addedAt: '2026-08-16', route: '/sepa' },
  { id: 'symbol-renames', label: '↪️ Renamed tickers now follow the company — SATS reads as ECHO and SQ as XYZ, with history joined across the change (SQ had been showing dead for 576 days)', addedAt: '2026-08-16', route: '/sepa' },
  { id: 'rotation-backtest', label: '🧪 Sector Rotation now shows whether acting on it pays — 116 monthly rebalances back to 2016: buying the top 3 sectors LOST to just holding all 11', addedAt: '2026-08-16', route: '/rotation' },
];

/** A feature stops highlighting this many days after it shipped. */
export const NEW_WINDOW_DAYS = 30;

/** True if `addedAt` is within the highlight window relative to `now`. */
export function isRecent(addedAt: string, now: Date, days = NEW_WINDOW_DAYS): boolean {
  const t = Date.parse(`${addedAt}T00:00:00`);
  if (Number.isNaN(t)) return false;
  const age = now.getTime() - t;
  return age >= -86_400_000 && age <= days * 86_400_000;   // shipped (≤1d future tol) & recent
}
