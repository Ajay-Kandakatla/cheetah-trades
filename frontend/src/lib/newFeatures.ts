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
