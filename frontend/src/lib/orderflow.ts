/* Pure presentation helpers for the Tape (order-flow) panel — kept out of the
 * component so they unit-test without rendering. */

export type TapeVerdict = 'BUY' | 'WAIT' | 'AVOID';

export type TapeCheck = { key: string; label: string; pass: boolean; detail: string };

export type TapeData = {
  found: boolean;
  symbol: string;
  et_date?: string;
  as_of_utc?: string;
  stale?: boolean;
  thin_tape?: boolean;
  last_price?: number;
  verdict?: TapeVerdict;
  reason?: string;
  checks?: TapeCheck[];
  checks_passed?: number;
  checks_total?: number;
  tape?: {
    delta: {
      buy_volume: number; sell_volume: number; delta: number;
      delta_pct_of_volume: number; classified_pct: number;
      late_delta: number; late_window_min: number;
      series: [string, number][]; n_trades: number;
    };
    big_prints: {
      threshold_dollars: number; buy_dollars: number; sell_dollars: number;
      prints: { time_et: string; price: number; size: number; dollars: number; side: string }[];
    };
    bursts: { time_et: string; side: string; dollars: number; volume: number; n_trades: number; price: number }[];
    truncated: boolean;
  };
  profile?: {
    poc: number; value_area_low: number; value_area_high: number;
    session_low: number; session_high: number; value_area_pct: number;
  } | null;
  emas?: {
    intraday: { pass: boolean; ema9: number | null; ema21: number | null; detail: string };
    daily: { pass: boolean; detail: string; source: string };
  };
  zone?: { state?: string | null; detail: string; nearest_support?: number | null; nearest_resistance?: number | null };
  gex?: { regime?: string; net_gex_dollars?: number; max_pain_strike?: number; expiration_date?: string; reliability?: string } | null;
  message?: string;
};

export function verdictView(v?: TapeVerdict | null): { label: string; icon: string; color: string; bg: string } {
  if (v === 'BUY') return { label: 'BUY signal', icon: '🟢', color: '#10b981', bg: 'rgba(16,185,129,0.12)' };
  if (v === 'AVOID') return { label: 'AVOID', icon: '🔴', color: '#ef4444', bg: 'rgba(239,68,68,0.12)' };
  return { label: 'WAIT', icon: '🟡', color: '#d97706', bg: 'rgba(217,119,6,0.12)' };
}

/** Compact dollars: 1234567 → "$1.2M". */
export function fmtDollars(d?: number | null): string {
  if (d == null || isNaN(d)) return '—';
  const a = Math.abs(d);
  const sign = d < 0 ? '−' : '';
  if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(0)}K`;
  return `${sign}$${a.toFixed(0)}`;
}

/** Signed share counts: 5021584 → "+5.0M sh". */
export function fmtShares(n?: number | null): string {
  if (n == null || isNaN(n)) return '—';
  const a = Math.abs(n);
  const sign = n > 0 ? '+' : n < 0 ? '−' : '';
  if (a >= 1e9) return `${sign}${(a / 1e9).toFixed(1)}B sh`;
  if (a >= 1e6) return `${sign}${(a / 1e6).toFixed(1)}M sh`;
  if (a >= 1e3) return `${sign}${(a / 1e3).toFixed(0)}K sh`;
  return `${sign}${a.toFixed(0)} sh`;
}

export function deltaTone(delta: number): { color: string; word: string } {
  if (delta > 0) return { color: '#10b981', word: 'buyers' };
  if (delta < 0) return { color: '#ef4444', word: 'sellers' };
  return { color: '#9ca3af', word: 'balanced' };
}

/** Downsample the per-minute cumulative-delta series to <= max points for the sparkline. */
export function sparklinePoints(series: [string, number][], max = 240): number[] {
  const vals = (series ?? []).map((p) => p[1]);
  if (vals.length <= max) return vals;
  const step = vals.length / max;
  const out: number[] = [];
  for (let i = 0; i < max; i++) out.push(vals[Math.min(vals.length - 1, Math.floor(i * step))]);
  out[out.length - 1] = vals[vals.length - 1]; // always end on the true final value
  return out;
}

/** Measured-record line for the accuracy strip. Honest about small n. */
export function accuracyLine(acc: { verdicts?: Record<string, { n: number; hit_1d_pct: number | null }> } | null): string | null {
  const buy = acc?.verdicts?.BUY;
  if (!buy || !buy.n) return null;
  if (buy.hit_1d_pct == null) return `${buy.n} BUY signal${buy.n === 1 ? '' : 's'} recorded — grading starts at T+1`;
  const caveat = buy.n < 30 ? ` (small n — wide error bars until ~30+)` : '';
  return `our measured record: ${buy.n} BUY signals, ${buy.hit_1d_pct}% up next day${caveat}`;
}
