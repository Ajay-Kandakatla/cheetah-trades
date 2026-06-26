/* Pure presentation helpers for the OpEx panel — kept out of the component so
 * they unit-test without rendering. */
export type ExpiryType = 'weekly' | 'monthly' | 'quad_witching';

export const EXPIRY_CHIP: Record<ExpiryType, { label: string; icon: string; weight: string }> = {
  quad_witching: { label: 'Quad-witching', icon: '⚡', weight: 'strongest pin' },
  monthly:       { label: 'Monthly · 3rd Fri', icon: '📅', weight: 'strong pin' },
  weekly:        { label: 'Weekly', icon: '·', weight: 'weak / transient pin' },
};

export function regimeView(regime?: string | null): { label: string; icon: string; color: string; blurb: string } {
  if (regime === 'pinning') {
    return { label: 'Pinning', icon: '📌', color: '#f59e0b',
      blurb: 'dealer hedging suppresses moves — expect a range / pin into expiry; breakouts likely stall' };
  }
  if (regime === 'amplifying') {
    return { label: 'Amplifying', icon: '🚀', color: '#a78bfa',
      blurb: 'dealer hedging feeds the move — a break has wind behind it; flushes can cascade' };
  }
  return { label: 'No gamma read', icon: '—', color: '#9ca3af', blurb: 'gamma data unavailable for this chain' };
}

/** Net GEX dollars → compact "$4.0M / 1%" style magnitude. */
export function fmtGex(d?: number | null): string {
  if (d == null) return '—';
  const a = Math.abs(d);
  const sign = d < 0 ? '−' : '+';
  if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(0)}K`;
  return `${sign}$${a.toFixed(0)}`;
}

/** Signed "X% above/below spot" for the max-pain magnet distance. */
export function magnetDistance(pctFromSpot?: number | null): string {
  if (pctFromSpot == null) return '';
  if (Math.abs(pctFromSpot) < 0.05) return 'at spot';
  return `${Math.abs(pctFromSpot).toFixed(1)}% ${pctFromSpot > 0 ? 'above' : 'below'} spot`;
}
