/* baseSetup — "real base" classifier for entry setups.

   Ajay 2026-06-22: across the SEPA list, Leaderboard, Top Picks and Breakouts,
   show only names with a DETECTED BASE by default — VCP, Power Play, or pocket
   pivot — and hide bare BREAKOUTs that have no base, unless the user toggles
   "show all". A bare breakout is the "non-VCP" name to keep out of the default
   view (Minervini pp.198-205: the base/contraction is what makes the breakout
   high-quality). */

export const BASE_SETUP_TYPES = ['VCP', 'POWER_PLAY', 'POCKET_PIVOT'] as const;

/** True when the setup is a real base (VCP / Power Play / pocket pivot), false
 *  for a bare BREAKOUT or no setup at all. */
export function isBaseSetup(type?: string | null): boolean {
  return type != null && (BASE_SETUP_TYPES as readonly string[]).includes(type);
}

/** Compact per-row setup badge (Ajay 2026-08-03: "show if something had a
 *  VCP" on the Breakouts board). Null for bare breakouts / no setup — the
 *  board stays quiet unless there's a real base to brag about. */
export function setupBadge(type?: string | null): { icon: string; label: string; title: string } | null {
  switch (type) {
    case 'VCP':
      return { icon: '📐', label: 'VCP',
               title: 'Volatility Contraction Pattern — the base tightened before this breakout (Minervini pp.198-205). The highest-quality launchpad.' };
    case 'POWER_PLAY':
      return { icon: '⚡', label: 'PP',
               title: 'Power Play — high-tight flag after a steep advance (Minervini Ch.7). Rare, aggressive base.' };
    case 'POCKET_PIVOT':
      return { icon: '🎯', label: 'PKT',
               title: 'Pocket pivot — up-day volume above every down-day volume of the last 10 sessions, inside the base.' };
    default:
      return null;
  }
}
