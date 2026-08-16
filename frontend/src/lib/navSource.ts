/* navSource — remembering which page sent you into a SEPA detail view.
 *
 * Ajay 2026-08-16: "The back button from Chartmaps is going to Sepa make it
 * track from sepa ticket to back to chartmaps please."
 *
 * The detail page already accepted `navigate('/sepa/X', { state: { from,
 * label } })`, but router state is ephemeral in two ways that both bite here:
 *
 *   1. `setSearchParams(next, { replace: true })` — how the detail page
 *      switches tabs — replaces the history entry WITHOUT carrying state
 *      forward, so the first tab click silently forgets where you came from.
 *   2. A reload, or a shared/bookmarked link, never had state to begin with.
 *
 * So the source also rides in the URL as `?from=<key>`, which survives both.
 * State stays the primary signal (it can carry a label the URL does not know),
 * and the query param is the durable fallback.
 */

export type NavSource = { path: string; label: string };

/** Pages that link INTO a SEPA detail view and want to be returned to.
 *  Keyed by a short slug so the URL stays readable and cannot be used to
 *  bounce a user to an arbitrary path. */
export const NAV_SOURCES: Record<string, NavSource> = {
  'chart-maps': { path: '/chart-maps', label: 'Chart Maps' },
};

/** Append `from=<key>` to a detail href, preserving any query it already has
 *  (the chart-map tiles ship `?tab=setup` / `?tab=supply`). Unknown keys are
 *  dropped rather than written, so the param can always be trusted on read. */
export function withSource(href: string, key: string): string {
  if (!href || !NAV_SOURCES[key]) return href;
  const [path, query = ''] = href.split('?');
  const params = new URLSearchParams(query);
  params.set('from', key);
  return `${path}?${params.toString()}`;
}

/** Where "← Back" should go. Router state wins — it may carry a label for a
 *  page not in the registry — then the URL param, then nothing (the caller
 *  falls back to browser history). */
export function resolveBack(
  state: { from?: string; label?: string } | null | undefined,
  fromParam: string | null | undefined,
): NavSource | null {
  if (state?.from) return { path: state.from, label: state.label || 'Back' };
  if (fromParam && NAV_SOURCES[fromParam]) return NAV_SOURCES[fromParam];
  return null;
}
