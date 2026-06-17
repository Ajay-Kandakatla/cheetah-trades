/* railBus — a tiny decoupled channel for opening the floating side rails
 * (WatchlistRail / PortfolioRail) from anywhere, without threading shared
 * state through the tree.
 *
 * On mobile (2026-06-16) the collapsed edge tabs are hidden because they sat
 * ON TOP of dense page content (the breakouts table — verdict pills clipped on
 * the right, row numbers covered on the left, far-right columns unreachable).
 * The NavBar's mobile action bar hosts the open buttons instead and dispatches
 * this event; each rail listens and slides its drawer in. Desktop keeps its
 * draggable edge tabs untouched. */

export type RailName = 'watchlist' | 'portfolio';

export const RAIL_OPEN_EVENT = 'cheetah:open-rail';

/** Ask a rail to open. No-op on the server (guarded for SSR/tests). */
export function openRail(which: RailName): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent<RailName>(RAIL_OPEN_EVENT, { detail: which }));
}
