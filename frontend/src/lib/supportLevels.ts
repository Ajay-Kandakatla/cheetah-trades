/* supportLevels — pure helpers for the Chart Maps "Support Levels" tab.
 *
 * Ajay 2026-08-19: "a new feature where I can look at support levels on demand
 * … toggle a drop down to check montly vs 3 months vs 6 months demand zones …
 * I should be able to a search of all the Ticker I do today … I want look at
 * recent support levels as well."
 *
 * Backend: backend/chart_maps/support.py (GET /chart-maps/support). Everything
 * here is formatting and coercion, so the component stays dumb and the numbers
 * are testable.
 *
 * NOT advice, and NOT a book method — `price_zones` is a configured
 * price-structure read and says so in its own header.
 */
import type { CmTile } from './chartMaps';

export type SupportWindow = { key: string; label: string; bars: number };

export type SupportLevel = {
  lo: number;
  hi: number;
  mid: number;
  /** The band's ORIGIN. A level that used to be overhead supply and now sits
   *  below price is support by polarity — a weaker claim than a floor that was
   *  bought four times, so it is shown rather than flattened away. */
  origin: 'demand' | 'supply';
  touches: number;
  strength: number;
  bars_since_test: number | null;
  oldest_touch_bars: number | null;
  recent: boolean;
  /** Price turned here more than once. A single-touch band is one swing
   *  low with synthetic width painted round it — and on a short zoom it is
   *  also the commonest, so it wins the nearest-first sort. Shown, but
   *  never presented as a floor. */
  tested: boolean;
  distance_pct: number | null;
  /** Overlay mode only — which zooms found this level, and how many agree.
   *  Agreement is the signal: a level only one window can see is usually an
   *  artifact of that window. */
  windows?: string[];
  agree?: number;
};

export type SupportPayload = {
  symbol: string;
  name?: string | null;
  window: string;
  window_label: string;
  windows: SupportWindow[];
  recent_bars: number;
  last_price?: number;
  bars_used?: number;
  /** Set when the frame could not cover the window asked for — a recent IPO.
   *  The label still says what was asked; this says what was read. */
  short_history?: { have: number; asked: number } | null;
  tile?: CmTile;
  supports?: SupportLevel[];
  overhead?: SupportLevel[];
  standing_in?: SupportLevel | null;
  levels_capped?: boolean;
  verdict?: { state?: string; entry_read?: string; label?: string } | null;
  params?: Record<string, number> | null;
  note?: string;
  disclaimer?: string;
  error?: string;
};

/** Shown before the first response lands so the dropdown is never empty.
 *  Mirrors backend SUPPORT_WINDOWS; the server's own list replaces it as soon
 *  as one arrives, so a change there does not need a frontend deploy. */
export const FALLBACK_WINDOWS: SupportWindow[] = [
  { key: '1m', label: '1 month', bars: 21 },
  { key: '3m', label: '3 months', bars: 63 },
  { key: '6m', label: '6 months', bars: 126 },
  { key: '1y', label: '1 year', bars: 252 },
  // The overlay pseudo-window: every zoom at once, clustered by agreement.
  { key: 'all', label: 'All windows · overlay', bars: 0 },
];

/** Matches backend support.DEFAULT_WINDOW. */
export const DEFAULT_WINDOW = '3m';

/** Coerce a `?window=` value against the list the server actually offers, so a
 *  key retired backend-side degrades to the default instead of 404ing. */
export function parseWindow(
  raw: string | null | undefined,
  offered: SupportWindow[] = FALLBACK_WINDOWS,
): string {
  const v = (raw || '').trim().toLowerCase();
  if (!v) return DEFAULT_WINDOW;
  return offered.some((w) => w.key === v) ? v : DEFAULT_WINDOW;
}

/** Coerce a typed ticker. Upper-cased and stripped of everything a US symbol
 *  cannot contain, so a pasted "$NVDA " or "nvda," still resolves. */
export function normalizeSymbol(raw: string | null | undefined): string {
  return (raw || '').toUpperCase().replace(/[^A-Z0-9.\-]/g, '').slice(0, 12);
}

export function supportQuery(p: { symbol: string; window: string }): string {
  const q = new URLSearchParams({ symbol: normalizeSymbol(p.symbol) });
  if (p.window && p.window !== DEFAULT_WINDOW) q.set('window', p.window);
  return q.toString();
}

/* ── formatting ───────────────────────────────────────────────────────────── */

export function money(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—';
  return `$${n.toFixed(2)}`;
}

/** The band, as a range. Never a single number: a support is a zone you place a
 *  stop under, and printing only the midpoint invites a stop inside it. */
export function bandLabel(lv: SupportLevel | null | undefined): string {
  if (!lv) return '—';
  return `${money(lv.lo)} – ${money(lv.hi)}`;
}

export function distanceLabel(
  lv: SupportLevel | null | undefined,
  side: 'support' | 'overhead' = 'support',
): string {
  if (!lv || lv.distance_pct == null || !Number.isFinite(lv.distance_pct)) return '—';
  const d = lv.distance_pct;
  // Under a rounding step from price, "+0.0%" reads as a formatting bug when
  // what it means is that the level is HERE — DHI's overhead sat 0.01% above
  // price on 2026-08-19, which is the whole reason that read mattered.
  if (Math.abs(d) < 0.05) return 'at price';
  if (side === 'overhead') return `+${d.toFixed(1)}%`;
  // A "support" whose distance came back negative is price already inside or
  // under it. Saying "-0.4% below" is nonsense; say where price actually is.
  if (d < 0) return `${Math.abs(d).toFixed(1)}% above`;
  return `${d.toFixed(1)}% below`;
}

/** How long ago the level was last touched, in trading sessions.
 *  `bars_since_test` is a bar count, so "sessions" is the honest unit —
 *  calling them days would be wrong across every weekend and holiday. */
export function recencyLabel(lv: SupportLevel | null | undefined): string {
  if (!lv || lv.bars_since_test == null || !Number.isFinite(lv.bars_since_test)) {
    return 'not tested in this window';
  }
  const n = Math.round(lv.bars_since_test);
  if (n <= 0) return 'tested today';
  if (n === 1) return 'tested yesterday';
  return `tested ${n} sessions ago`;
}

/** The evidence behind a level, in one phrase. Touch count leads because it is
 *  the thing that makes a price a level at all; strength is relative to the
 *  other bands IN THIS WINDOW and is meaningless across zooms, so it trails. */
export function evidenceLabel(lv: SupportLevel | null | undefined): string {
  if (!lv) return '—';
  const t = lv.touches ?? 0;
  const touches = t === 1 ? '1 touch' : `${t} touches`;
  // Overlay rows lead with agreement — it outranks everything else on the row.
  // "one window only" is spelled out because in this view that IS the caveat.
  if (lv.agree != null && lv.windows?.length) {
    const who = lv.windows.join(', ');
    const head = lv.agree >= 2
      ? `${lv.agree} windows agree (${who})`
      : `one window only (${who})`;
    const weakO = lv.tested ? '' : ' · single low';
    return `${head} · ${touches}${weakO}`;
  }
  const polarity = lv.origin === 'supply' ? ' · was resistance' : '';
  // Spelled out rather than left to be inferred from "1". This is the level a
  // stop goes under, and the difference between a floor and a bar is the whole
  // question.
  const weak = lv.tested ? '' : ' · single low';
  return `${touches}${weak}${polarity}`;
}

/** One line under the ticker: where price is standing right now. */
export function headline(p: SupportPayload | null | undefined): string {
  if (!p) return '';
  if (p.error) return p.error;
  if (p.standing_in) {
    return `Price is INSIDE a band at ${bandLabel(p.standing_in)} — `
      + `${evidenceLabel(p.standing_in)}, ${recencyLabel(p.standing_in)}.`;
  }
  const sup = (p.supports || [])[0];
  if (!sup) return `No band below ${money(p.last_price)} in this window.`;
  const caveat = sup.tested ? '' : ' Single swing low, not a tested floor.';
  return `Nearest support ${bandLabel(sup)} · ${distanceLabel(sup)} · `
    + `${evidenceLabel(sup)} · ${recencyLabel(sup)}.${caveat}`;
}

/** How many of the listed supports were tested inside the recency window.
 *  Ajay asked for "recent support levels as well", so the count is stated
 *  rather than left to be counted off the table. */
export function recentCount(levels: SupportLevel[] | null | undefined): number {
  return (levels || []).filter((l) => l.recent).length;
}

/** The warning shown when the frame was shorter than the window asked for.
 *  Empty string when there is nothing to warn about — a recent IPO is ordinary,
 *  but a chart labelled "6 months" that holds 30 bars is not. */
export function shortHistoryNote(p: SupportPayload | null | undefined): string {
  const s = p?.short_history;
  if (!s || !s.have || !s.asked) return '';
  return `Only ${s.have} sessions of history — less than the ${s.asked} `
    + `this window asks for. Levels are read from what exists.`;
}

/** How many of the listed supports price turned at more than once.
 *  Deliberately separate from `recentCount`: neither implies the other. A level
 *  touched yesterday once is recent and untested; one turned at four times last
 *  year is tested and stale. */
export function testedCount(levels: SupportLevel[] | null | undefined): number {
  return (levels || []).filter((l) => l.tested).length;
}
