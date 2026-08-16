/* Sector rotation — pure helpers for the /rotation page.
 *
 * Ajay 2026-08-16: "I want you to have sector rotation tracker what I feel now
 * is money is rotating out of that themes I gave you."
 *
 * Every number the page renders is computed on the backend
 * (backend/rotation/tracker.py). Nothing here recomputes a return — these
 * functions only decide how a measured number is SHOWN, which keeps the two
 * sides from ever disagreeing about what a percentage means.
 */

export type RotRow = {
  group: string;
  n: number;
  dropped: number;
  dropped_symbols?: string[];
  median_window: number | null;
  median_21d: number | null;
  median_63d: number | null;
  rel_window: number | null;
  rel_21d: number | null;
  rel_63d: number | null;
  pct_positive: number | null;
  stance?: 'defensive' | 'cyclical' | 'commodity' | null;
  etf?: string;
  etf_window?: number | null;
  etf_vs_median?: number | null;
};

export type RotBoard = {
  start: string;
  as_of: string;
  benchmark: { symbol: string; window: number | null; d21: number | null; d63: number | null };
  sectors: RotRow[];
  themes: RotRow[];
  havens: RotRow[];
  stance: { defensive: number | null; cyclical: number | null; commodity: number | null };
  leaders: string[];
  laggards: string[];
  sampled?: Record<string, { of: number; used: number }>;
  unmapped?: number;
  note?: string;
  cached?: boolean;
  error?: string;
};

/** Relative performance in percentage POINTS. The unit matters: a sector that
 *  rose 4% while equal-weight rose 6.7% is -2.7pp, not -2.7%. Writing it as %
 *  invites reading it as an absolute loss when the group actually went up. */
export function pp(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}pp`;
}

export function pct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;
}

/** Colour tone for a relative number. Zero is neutral, not green — a group
 *  exactly matching the benchmark has not rotated. */
export function tone(v: number | null | undefined): 'up' | 'down' | 'flat' {
  if (v == null || !Number.isFinite(v) || v === 0) return 'flat';
  return v > 0 ? 'up' : 'down';
}

/** A group whose members are mostly dead tickers has a median worth little.
 *  The backend already drops them; this decides when to SAY so. */
export const THIN_GROUP_N = 5;

export function isThinGroup(r: Pick<RotRow, 'n'>): boolean {
  return (r?.n ?? 0) < THIN_GROUP_N;
}

/** Did the recent window disagree with the full window? That disagreement is
 *  the single most decision-relevant thing on the page — it is how you tell a
 *  finished trend from one that just turned. */
export function turned(r: Pick<RotRow, 'rel_window' | 'rel_21d'>): 'up' | 'down' | null {
  const { rel_window: full, rel_21d: recent } = r || ({} as RotRow);
  if (full == null || recent == null) return null;
  if (full < 0 && recent > 0) return 'up';
  if (full > 0 && recent < 0) return 'down';
  return null;
}

/** One honest line about the ETF-vs-median gap. A large positive gap means the
 *  ETF looks better than the typical member — mega-cap concentration hiding
 *  damage in the names you would actually buy. */
export function etfGapLine(r: Pick<RotRow, 'etf' | 'etf_vs_median'>): string | null {
  const g = r?.etf_vs_median;
  if (g == null || !Number.isFinite(g) || Math.abs(g) < 2) return null;
  const who = g > 0 ? r.etf : 'the median stock';
  const hidden = g > 0 ? 'hides' : 'overstates';
  return `${who} ${hidden} the move by ${Math.abs(g).toFixed(1)}pp`;
}

/** Defensive minus cyclical, in points. Positive = money hiding. Ajay asked
 *  for "safe haves vs in general" as a single read. */
export function riskStance(s: RotBoard['stance']): { label: string; spread: number | null } {
  const d = s?.defensive;
  const c = s?.cyclical;
  if (d == null || c == null) return { label: 'unknown', spread: null };
  const spread = d - c;
  if (spread > 2) return { label: 'defensive leading', spread };
  if (spread < -2) return { label: 'cyclicals leading', spread };
  return { label: 'no clear stance', spread };
}

export function boardQuery(o: { start?: string; refresh?: boolean }): string {
  const p = new URLSearchParams();
  if (o.start) p.set('start', o.start);
  if (o.refresh) p.set('refresh', 'true');
  const q = p.toString();
  return q;
}

/** Window presets. "Since June" is Ajay's own framing of the current move. */
export const WINDOWS = [
  { key: '2026-06-01', label: 'Since June' },
  { key: '2026-01-01', label: 'Year to date' },
  { key: '2026-07-16', label: 'Last month' },
];
