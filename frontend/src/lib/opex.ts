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

/** Input shape for the caveman translation — the slice of OpexData it reads. */
export type CavemanInput = {
  days_to_expiry?: number;
  expiration_date?: string;
  max_pain?: { max_pain_strike: number; pct_from_spot?: number | null; max_pain_tie?: boolean } | null;
  gamma?: { regime?: string | null; put_wall?: number | null; call_wall?: number | null } | null;
  gex_reliability?: string;
};

/** Dynamic plain-English rewrite of the panel's numbers (Ajay 2026-07-06:
 * "I do not understand the jargon… caveman translation, dynamically").
 * Pure — returns one short sentence per line, derived from the live values. */
export function cavemanSummary(d: CavemanInput): string[] {
  const lines: string[] = [];
  const mp = d.max_pain;
  const g = d.gamma;
  const date = d.expiration_date ?? 'expiration';
  const dte = d.days_to_expiry;

  if (mp) {
    const pct = mp.pct_from_spot;
    const strike = `$${mp.max_pain_strike}`;
    if (pct == null || Math.abs(pct) < 1) {
      lines.push(`Price is already sitting on the magnet (${strike}) — the options money is happiest right here, so expect it to stay glued near ${strike} into ${date}.`);
    } else if (pct > 0) {
      lines.push(`The options money wants this stock HIGHER: the magnet (${strike}) sits ${Math.abs(pct).toFixed(1)}% above today's price, so a slow drift UP toward ${strike} into ${date} is slightly favored.`);
    } else {
      lines.push(`The options money wants this stock LOWER: the magnet (${strike}) sits ${Math.abs(pct).toFixed(1)}% below today's price, so a drift DOWN toward ${strike} into ${date} is slightly favored.`);
    }
  }

  if (g?.regime === 'pinning') {
    lines.push(`Right now the market makers act like a BRAKE: they sell when it rallies and buy when it dips, so moves get smothered — a big breakout before ${date} is less likely.`);
  } else if (g?.regime === 'amplifying') {
    lines.push(`Right now the market makers act like a TAILWIND: whichever way the stock moves, their hedging pushes it further — rallies run hotter, drops fall harder.`);
  }

  if (g && g.put_wall != null && g.call_wall != null) {
    lines.push(`Think of $${g.put_wall}–$${g.call_wall} as the playing field until then: heavy hedging near $${g.put_wall} acts like a floor, near $${g.call_wall} like a ceiling.`);
  }

  if (dte != null && dte > 25) {
    lines.push(`Still ${dte} days out — this pull is weak for now and gets strongest in the final week.`);
  } else if (dte != null && dte <= 5) {
    lines.push(`Final days — the pull is at its strongest right now; after ${date} it resets.`);
  }

  if (d.gex_reliability === 'single_name' && g?.regime) {
    lines.push(`This is a single stock (not an index), so the brake/tailwind read can be wrong — trust the magnet number more than the label.`);
  }

  return lines;
}
