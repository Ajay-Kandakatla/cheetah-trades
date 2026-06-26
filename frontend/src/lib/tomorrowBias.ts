/* Pure presentation helpers for the Tomorrow Bias badge — kept out of the
 * component so they unit-test without rendering (Vitest). */
import type { Lean, ConfTier } from '../hooks/useTomorrowBias';

export const LEAN_VISUAL: Record<Lean, { label: string; color: string; arrow: string }> = {
  LEAN_UP:   { label: 'Lean up',   color: '#10b981', arrow: '▲' },
  LEAN_DOWN: { label: 'Lean down', color: '#ef4444', arrow: '▼' },
  NEUTRAL:   { label: 'Flat',      color: '#9ca3af', arrow: '●' },
};

export const TIER_COLOR: Record<ConfTier, string> = {
  HIGH: '#10b981', MEDIUM: '#f59e0b', LOW: '#9ca3af',
};

/** Human-readable caveat for an engine flag. Unknown flags pass through
 *  prettified (snake_case → spaces) so a new backend flag never renders raw. */
export function flagLabel(flag: string): string {
  const known: Record<string, string> = {
    thin_print: '⚠️ thin after-hours print — fades by morning',
    gap_fading: '⚠️ gap fading off its extreme',
    event_risk: '🎲 event / earnings night — trade the range, not a direction',
    inside_expected_move: 'ℹ️ move is inside what options already priced',
    high_vix: '⚠️ VIX elevated — gaps fill more often',
    fighting_the_tape: '⚠️ strong vs the market tape — confirm before sizing',
    options_pillar_partial: 'ℹ️ options read is half-data (no SOIR percentile yet)',
    options_conflict: 'ℹ️ options volume vs OI disagree — options pillar muted',
    no_options_data: 'ℹ️ no options snapshot yet',
    no_eh_data: 'ℹ️ no extended-hours move yet',
    stale_eh: 'ℹ️ extended-hours window has passed',
    indices_disagree: '⚠️ SPY and QQQ disagree overnight',
    vix_proxy_only: 'ℹ️ VIX direction unconfirmed (not counted)',
    breadth_unavailable: 'ℹ️ overnight breadth not wired this run',
  };
  if (known[flag]) return known[flag];
  if (flag.startsWith('earnings_source:')) {
    const src = flag.split(':')[1];
    return `ℹ️ earnings inferred from ${src === 'iv_inferred' ? 'implied volatility' : 'news'}`;
  }
  return flag.replace(/_/g, ' ');
}

/** Confidence as a one-word tier + the 0-100 number, e.g. "HIGH · 78". */
export function confLabel(tier: ConfTier, confidence?: number): string {
  return confidence == null ? tier : `${tier} · ${confidence}`;
}
