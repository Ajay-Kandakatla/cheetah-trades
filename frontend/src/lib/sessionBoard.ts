/* sessionBoard — pure helpers for the Session tab (/chart-maps?tab=session).
 *
 * Ajay 2026-08-31: "Can you create a tab for ORB/ FVG/ Bullish sentiment or
 * bearish for all the onces in demand zone. and deep demand zones ... I will
 * use this tab after market open to figure out market sentiment."
 *
 * Backend: backend/supply_demand/session_board.py
 * (GET /supply-demand/session-board). The daily boards answer WHICH NAMES;
 * this answers whether the session is confirming the daily band that listed
 * them. Everything here is pure so the component stays dumb and testable.
 *
 * Mood, fair-value gaps and the SMC sequence are CONVENTION, not book methods.
 * NOT advice.
 */

export type Bias = 'bullish' | 'bearish' | 'neutral' | 'unknown';
export type OrbState = 'above' | 'below' | 'inside' | null;

export type Orb = {
  lo: number; hi: number; mid: number;
  minutes: number; bars: number; session: string;
  /** False while the window is still filling. At 09:31 a "15-minute range"
   *  is one bar — real, but not yet the level, and it must not read as one. */
  complete?: boolean;
  bars_needed?: number;
};

export type SessionGap = {
  kind: 'demand' | 'supply';
  lo: number; hi: number; mid: number;
  width_pct?: number; fill_pct?: number;
  displacement_atr?: number; at?: string;
};

export type SmcRead = {
  setups: any[]; count: number;
  best_grade: number | null; cited?: boolean;
};

export type MoodRead = {
  score: number | null; label: string;
  components?: Record<string, any>;
  unavailable?: string[]; bars?: number;
};

export type SessionRow = {
  symbol: string;
  name?: string | null;
  sources?: string[];
  theme?: string | null;
  last_price: number | null;
  band: { kind: string; lo: number; hi: number; mid: number } | null;
  at_band: boolean;
  mood: MoodRead | null;
  orb: Orb | null;
  orb_state: OrbState;
  fair_value_gaps: SessionGap[];
  session_gaps: SessionGap[];
  smc: SmcRead | null;
  signal: { action: string; reasons?: string[]; blockers?: string[]; trade?: any } | null;
  bias: Bias;
  /** Ranking only — CONVENTION. null when mood could not be read, which sorts
   *  last and must never render as a zero (a real neutral reading). */
  session_score: number | null;
  session: string | null;
  tf: string;
  tf_label?: string;
  bars: number;
  unavailable: string[];
};

export type SessionPayload = {
  rows: SessionRow[];
  count: number;
  unreadable?: number;
  tf: string;
  tf_options?: { key: string; label: string }[];
  session: string | null;
  live?: boolean;
  orb_minutes?: number;
  as_of?: string | null;
  age_sec?: number;
  elapsed_sec?: number;
  cached?: boolean;
  warming?: boolean;
  note?: string;
  weights?: Record<string, number>;
  disclaimer?: string;
};

export const BIAS_ORDER: Bias[] = ['bullish', 'neutral', 'bearish', 'unknown'];

export const BIAS_META: Record<Bias, { label: string; tone: string; dot: string }> = {
  bullish: { label: 'Bullish', tone: 'good', dot: '▲' },
  bearish: { label: 'Bearish', tone: 'poor', dot: '▼' },
  neutral: { label: 'Neutral', tone: 'muted', dot: '●' },
  unknown: { label: 'No read', tone: 'muted', dot: '–' },
};

/** Where price sits against the opening range, in words.
 *
 *  A FORMING range says so instead of pretending. Crabel's premise is about
 *  the session's first agreed value; "above the first 2 of 15 minutes" is not
 *  that, and a board Ajay opens at 09:31 would otherwise show 99 confident
 *  breakout reads built on one bar each.
 */
export function orbLabel(orb: Orb | null | undefined, state: OrbState): string {
  if (!orb) return 'no opening range';
  if (orb.complete === false) {
    const left = orb.bars_needed ?? 0;
    return left > 0 ? `range forming (${orb.bars}/${orb.minutes}m)` : 'range forming';
  }
  if (state === 'above') return `above the ${orb.minutes}m range`;
  if (state === 'below') return `below the ${orb.minutes}m range`;
  if (state === 'inside') return `inside the ${orb.minutes}m range`;
  return `${orb.minutes}m range set`;
}

/** True when the ORB is complete AND price has taken a side. */
export function orbBroken(orb: Orb | null | undefined, state: OrbState): boolean {
  return !!orb && orb.complete !== false && (state === 'above' || state === 'below');
}

/** The short "why is this row here" chips, most decisive first.
 *
 *  Each chip is a FACT that contributed to the ranking, so the score is always
 *  traceable on the row rather than being a number the reader has to trust.
 */
export function reasonChips(row: SessionRow): { text: string; tone: string }[] {
  const out: { text: string; tone: string }[] = [];
  if (row.at_band) out.push({ text: 'at the daily band', tone: 'good' });
  const n = row.smc?.count ?? 0;
  if (n > 0) {
    const g = row.smc?.best_grade;
    out.push({ text: `SMC setup${n > 1 ? ` ×${n}` : ''}${g != null ? ` · ${g}` : ''}`, tone: 'good' });
  }
  if (orbBroken(row.orb, row.orb_state)) {
    out.push({ text: orbLabel(row.orb, row.orb_state),
               tone: row.orb_state === 'above' ? 'good' : 'poor' });
  }
  if (row.session_gaps?.length) {
    out.push({ text: `${row.session_gaps.length} gap${row.session_gaps.length > 1 ? 's' : ''} this session`, tone: 'good' });
  }
  const act = row.signal?.action;
  if (act === 'BUY' || act === 'SELL') {
    out.push({ text: act, tone: act === 'BUY' ? 'good' : 'poor' });
  }
  return out;
}

/** Board headline: how the session reads across every name on it. */
export function biasTally(rows: SessionRow[]): Record<Bias, number> {
  const out: Record<Bias, number> = { bullish: 0, bearish: 0, neutral: 0, unknown: 0 };
  for (const r of rows || []) out[r.bias in out ? r.bias : 'unknown'] += 1;
  return out;
}

/** "58 demand · 42 deep" — where the names came from. */
export function sourceLabel(sources: string[] | undefined): string {
  if (!sources || !sources.length) return '';
  return sources.map((s) => (s === 'deep' ? 'Deep' : 'Demand')).join(' + ');
}

/** Session stamp. Out of hours it must say WHICH session, never imply today. */
export function sessionLabel(p: Pick<SessionPayload, 'session' | 'live'>): string {
  if (!p.session) return 'no session data';
  if (p.live) return `live · ${p.session}`;
  return `last session · ${p.session}`;
}

export function filterRows(rows: SessionRow[], bias: Bias | 'all',
                           atBandOnly: boolean, setupsOnly: boolean): SessionRow[] {
  return (rows || []).filter((r) => {
    if (bias !== 'all' && r.bias !== bias) return false;
    if (atBandOnly && !r.at_band) return false;
    if (setupsOnly && !(r.smc?.count)) return false;
    return true;
  });
}
