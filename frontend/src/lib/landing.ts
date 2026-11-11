import type { CmTab } from './chartMaps';

/* landing — where "/" sends a signed-in user.
 *
 * Ajay 2026-09-07: "Make chart maps default loading page for me on the app
 * load. Also for everyone." Chart Maps leads both chains now (it is granted to
 * every account by default since access catalog v24). The rest of each chain
 * is the 2026-06-23 order (SEPA Global as the universal front door, then the
 * owner's scanner pages / the friends' pages), kept as the fallback for an
 * account that hid Chart Maps. First accessible feature wins; null = nothing
 * accessible, and the router shows 404 rather than looping.
 */
export const LANDING_ORDER: { admin: readonly string[]; user: readonly string[] } = {
  admin: ['chart-maps', 'sepa-global', 'sepa', 'portfolio', 'morning', 'leaderboard', 'todos', 'notifications'],
  user: ['chart-maps', 'sepa-global', 'breakouts', 'sepa', 'morning', 'food', 'kids', 'todos', 'notifications', 'glossary'],
};

export const LANDING_FEATURE = 'chart-maps';

/** The route to land on, or null when none of the chain is accessible. */
export function pickLanding(features: Set<string> | readonly string[], isAdmin: boolean): string | null {
  const has = features instanceof Set ? features : new Set(features);
  for (const id of (isAdmin ? LANDING_ORDER.admin : LANDING_ORDER.user)) {
    if (has.has(id)) return `/${id}`;
  }
  return null;
}

/** 🚩 The Chart Maps tab "/" opens for the PRIMARY OWNER (one account,
 *  `is_primary_admin` from /auth/me — never an email in the bundle).
 *
 *  Ajay 2026-11-10: "Then default my landing page to Gajjala's tab in
 *  chartmaps on the app always." His LANDING only: the bare /chart-maps
 *  (DEFAULT_TAB = CM_TABS[0]) and the CM_TABS order are untouched, so every
 *  other viewer, the menu's Chart Maps link and a hand-typed /chart-maps keep
 *  today's board. Type-only import: chartMaps.ts stays out of the entry chunk. */
export const OWNER_LANDING_TAB: CmTab = 'gajjala';

/** The "/" destination after pickLanding. The primary owner whose winning
 *  feature is Chart Maps gets `?tab=` + OWNER_LANDING_TAB (the same `tab`
 *  param chartMaps.tabSearch writes — landing.test pins the two equal);
 *  every other viewer and every other target come back byte for byte. */
export function ownerLanding(target: string | null, isPrimaryOwner: boolean): string | null {
  if (!isPrimaryOwner || target !== `/${LANDING_FEATURE}`) return target;
  return `${target}?${new URLSearchParams({ tab: OWNER_LANDING_TAB }).toString()}`;
}
