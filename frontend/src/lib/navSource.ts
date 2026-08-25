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
  // Ajay 2026-08-17: "Take me to the setup tab direct from chart maps and
  // demand zone page". The Back in Demand panel already passed router state,
  // which is enough for the back button UNTIL the first tab click replaces the
  // history entry and drops it — exactly the bug this module exists to fix.
  'supply-demand': { path: '/supply-demand', label: 'Supply & Demand' },
  // Ajay 2026-08-24: "back button from supply demand doesnt take me to same
  // page ... it goes to sepa always". The zones list page is part of the same
  // family and had the same raw-Link problem.
  'demand-zones': { path: '/demand-zones', label: 'Demand Zones' },
};

/** The registry, read backwards: which source key does a pathname belong to?
 *
 *  This exists because the durable `?from=` signal was OPT-IN per callsite,
 *  and callsites forgot. Router state covers a plain click, but a Cmd-click,
 *  middle-click or `window.open` starts a fresh tab with NO state and NO
 *  history — the detail page's back button then falls through to its hard
 *  `/sepa` default, which is exactly the bug Ajay hit from Supply & Demand.
 *  Deriving the key from where the link is RENDERED makes the durable signal
 *  automatic for every registered page instead of a per-link chore.
 *
 *  Prefix match, longest first, so '/supply-demand/anything' still resolves
 *  and a future '/demand-zones-x' route cannot be claimed by '/demand-zones'. */
export function sourceKeyFor(pathname: string | null | undefined): string | null {
  const p = (pathname || '').split('?')[0];
  let best: string | null = null;
  let bestLen = 0;
  for (const [key, src] of Object.entries(NAV_SOURCES)) {
    if (src.path.length <= bestLen) continue;
    if (p === src.path || p.startsWith(src.path + '/')) {
      best = key;
      bestLen = src.path.length;
    }
  }
  return best;
}

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
