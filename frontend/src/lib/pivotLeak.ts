/* Leaky-pivot chip logic — pure, shared by the general SEPA card (and any
 * future surface). Backend rule: sepa/pivot_leakage.py (Minervini X 2026
 * "pivot leakage") — the SAME read the Auto-Pilot intraday trigger enforces,
 * stamped on scan rows as `pivot_leakage`. The chip only shows where it can
 * change a decision: a buyable / setup-ready name whose pivot is leaking. */

export type PivotLeakage = {
  leaky?: boolean;
  leaks?: number;
  last_leak_bars_ago?: number | null;
} | null | undefined;

export type LeakChip = { label: string; title: string };

export function leakChip(
  leakage: PivotLeakage,
  opts: { buyable?: boolean; setupReady?: boolean },
): LeakChip | null {
  if (!leakage || leakage.leaky !== true) return null;
  if (!opts.buyable && !opts.setupReady) return null;
  const n = typeof leakage.leaks === 'number' ? leakage.leaks : null;
  const ago = typeof leakage.last_leak_bars_ago === 'number' ? leakage.last_leak_bars_ago : null;
  return {
    label: '🚱 leaky pivot',
    title:
      `Poked above the pivot but closed back below it ${n ?? 'several'} time${n === 1 ? '' : 's'} recently` +
      (ago != null ? ` (last: ${ago} day${ago === 1 ? '' : 's'} ago)` : '') +
      '. Minervini (2026): right-side volatility "often starts as pivot leakage" — ' +
      'wait for a close that HOLDS above the pivot. Auto-Pilot skips same-day entries on these.',
  };
}
