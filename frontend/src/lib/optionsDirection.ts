/* netDirection — a plain Bullish / Bearish / Neutral read for a SOIR row.
 *
 * The Schaeffer SOIR "signal" (BULLISH/BEARISH/WATCH/NEUTRAL) is the CONTRARIAN
 * options-crowd read — it's often NEUTRAL ("no contrarian edge") even when the
 * stock itself is clearly trending. That confused the read ("trend up but it
 * says NEUTRAL — bull or bear?"). This gives the stock's own directional
 * posture (trend + fundamentals), kept separate from the contrarian signal. */
export type NetDir = {
  label: 'Bullish' | 'Bearish' | 'Neutral';
  color: string;
  icon: string;
  why: string;
};

export function netDirection(row: {
  trend?: string | null;
  sepa_score?: number | null;
  pillars?: { trend?: string | null; fundamental_score?: number | null } | null;
}): NetDir {
  const trend = String(row.pillars?.trend ?? row.trend ?? '').toLowerCase();
  const fund = row.pillars?.fundamental_score ?? row.sepa_score ?? null;
  const fundTxt = fund != null ? ` · fundamentals ${Math.round(fund)}/100` : '';
  if (trend.includes('up') || trend.includes('bull')) {
    return { label: 'Bullish', color: '#10b981', icon: '📈', why: `Uptrend${fundTxt}` };
  }
  if (trend.includes('down') || trend.includes('bear')) {
    return { label: 'Bearish', color: '#ef4444', icon: '📉', why: `Downtrend${fundTxt}` };
  }
  return { label: 'Neutral', color: '#9ca3af', icon: '➖', why: `No clear trend${fundTxt}` };
}
