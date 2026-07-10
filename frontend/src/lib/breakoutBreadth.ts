/* Pure helpers for the Breakout Breadth strip — unit-tested without render. */

export type BreadthRead = { state: 'EXPANDING' | 'HEALTHY' | 'MIXED' | 'HOSTILE'; icon: string; label: string; guidance: string };

export type BreadthData = {
  ok: boolean;
  reason?: string;
  today?: { date_et: string; n_breakouts: number };
  avg10?: number;
  recent_graded?: { n: number; followed_through: number; failed: number; stalled: number; failure_rate: number | null; window_bars: number };
  read?: BreadthRead;
  series?: { date_et: string; n: number; failure_rate: number | null }[];
  boundary?: string;
};

export function readColor(state?: string): string {
  if (state === 'EXPANDING' || state === 'HEALTHY') return '#10b981';
  if (state === 'HOSTILE') return '#ef4444';
  return '#d97706';
}

/** "36 today vs 121 avg" delta line with an honest direction word. */
export function countLine(today?: number, avg10?: number): string {
  if (today == null) return '—';
  if (!avg10) return `${today} breakouts today`;
  const ratio = today / avg10;
  const word = ratio >= 1.25 ? 'expanding' : ratio <= 0.6 ? 'contracting' : 'steady';
  return `${today} today vs ${Math.round(avg10)} avg — ${word}`;
}

/** Follow-through split for the mini bar: fractions that sum to 1 (or null). */
export function ftSplit(g?: BreadthData['recent_graded']):
  { ft: number; fail: number; stall: number } | null {
  if (!g || !g.n) return null;
  return { ft: g.followed_through / g.n, fail: g.failed / g.n, stall: g.stalled / g.n };
}
