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
