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
