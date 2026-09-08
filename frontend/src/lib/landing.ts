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
