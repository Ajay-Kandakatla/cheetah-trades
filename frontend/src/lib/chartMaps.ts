/* chartMaps — pure helpers for the Chart Maps study board (/chart-maps).
 *
 * Ajay 2026-08-15: "I need just maps that you are pulling show… look at
 * patterns and learn them day by day."
 *
 * Backend: backend/chart_maps/board.py (GET /chart-maps?tab=…). The server
 * returns ONE tile shape for all three tabs; everything here is geometry and
 * formatting, so the drawing component stays dumb and the numbers are testable.
 *
 * NOT advice — a study surface over scans that already exist.
 */
import { layoutLabels, type LabelItem } from './zonePlan';
import type { DemandScanProgress } from './demandScanProgress';

export type CmTab = 'vcp' | 'zones' | 'winners';
export const CM_TABS: CmTab[] = ['vcp', 'zones', 'winners'];

export const TAB_META: Record<CmTab, { label: string; blurb: string }> = {
  vcp: {
    label: 'Strong VCP',
    blurb: 'Bases whose contractions have tightened — the volatility squeeze before a breakout. Green box is the base, dashed lines the pivot and the stop.',
  },
  zones: {
    label: 'Back in Demand',
    blurb: 'Names that left a demand zone and have pulled back into it. Green band is the zone, with the buy / stop / target written on.',
  },
  winners: {
    label: 'Past Winners',
    blurb: 'Setups from your own ledger that reached their measure-rule target before their stop. The dotted line is the confirmation bar — study what the base looked like BEFORE it.',
  },
};

export type CmBar = { t: string; o: number; h: number; l: number; c: number; v: number };
export type CmBand = { kind: 'base' | 'demand' | 'supply'; lo: number; hi: number; label?: string };
export type CmLineTone = 'buy' | 'stop' | 'target' | 'now';
export type CmLine = { price: number; label: string; tone: CmLineTone };
export type CmMarker = { date: string; label?: string; kind?: string };
export type CmStat = { k: string; v: string };
export type CmBadge = { text: string; tone: 'good' | 'warn' | 'muted' };

export type CmTile = {
  symbol: string;
  name?: string | null;
  href: string;
  bars: CmBar[];
  bands: CmBand[];
  lines: CmLine[];
  markers: CmMarker[];
  stats: CmStat[];
  why: string;
  theme?: string | null;
  badges?: CmBadge[];
  pattern?: string | null;
};

export type CmPatternRecord = {
  pattern: string; label: string;
  wins: number; losses: number; n: number; win_pct: number | null;
};

export type CmSort = { key: string; label: string };

export type CmBoard = {
  tab: CmTab;
  count: number;
  /** The sort actually applied. The winners tabs read a ledger with no live
   *  volume, so the backend answers `theme` there and sends an empty `sorts`. */
  sort?: string;
  sorts?: CmSort[];
  /** Liquidity floor by 50-day average $ volume, same tiers as Back in Demand. */
  min_tier?: string;
  tiers?: CmSort[];
  /** How many names the floor removed. Shown so a shrunken board is explained
   *  rather than just smaller. */
  dropped_thin?: number;
  /** Sorts that need an intraday tape pull, and how far it got. */
  tape_sorts?: string[];
  tape_pool?: number;
  tape_enriched?: number;
  /** Set when the chosen sort's column came back empty for every row — the
   *  board is showing its default order and says so. */
  sort_unavailable?: string | null;
  tiles: CmTile[];
  disclaimer?: string;
  note?: string;
  warming?: boolean;
  /* The demand tab's live scan counter. Same scan the Back in Demand tab on
   * /supply-demand watches — both tabs read one demand_reentry cache, so they
   * must show one progress reading (Ajay 2026-08-17). */
  progress?: DemandScanProgress | null;
  matched?: number;
  scanned?: number;
  universe_key?: string;
  universe_label?: string;
  generated_at?: string | number | null;
  scan_generated_at?: string | number | null;
  patterns?: string[];
  excluded_already_past_target?: number;
  record?: {
    overall: { wins: number; losses: number; n: number; win_pct: number | null };
    by_pattern: CmPatternRecord[];
    caveat: string;
  };
};

/* ── tab plumbing ─────────────────────────────────────────────────────────── */

/** Coerce a `?tab=` value. An unknown tab lands on the first one rather than
 *  rendering an empty board — a mistyped deep link should still show charts. */
export function parseTab(raw: string | null | undefined): CmTab {
  const t = (raw || '').trim().toLowerCase();
  return (CM_TABS as string[]).includes(t) ? (t as CmTab) : 'vcp';
}

/** Deep link to a ticker's SEPA detail page, on the tab that shows the same
 *  geometry the tile drew. SepaCandidate silently falls back to its `chart`
 *  tab on an unknown value, so a typo here is invisible — hence the test. */
export function sepaHref(symbol: string, tab: 'setup' | 'supply' | 'breakout' = 'setup'): string {
  return `/sepa/${encodeURIComponent((symbol || '').toUpperCase())}?tab=${tab}`;
}

/** Which ledger the Past Winners tab reads. Ajay 2026-08-16: "In the past
 *  winners tab I wanna see the deman zones that were successful as well." */
export type WinnerSource = 'pattern' | 'zone';

export const WINNER_SOURCES: { key: WinnerSource; label: string }[] = [
  { key: 'pattern', label: 'Chart patterns' },
  { key: 'zone', label: 'Demand zones' },
];

export function parseSource(v: string | null | undefined): WinnerSource {
  return v === 'zone' ? 'zone' : 'pattern';
}

/** Matches board.DEFAULT_SORT. Kept out of the query string when unchanged so
 *  a shared URL stays short and the default stays the default. */
export const DEFAULT_SORT = 'theme';

/** Matches board.DEFAULT_MIN_TIER — "comfortably tradeable in retail size"
 *  ($10M/day). Ajay 2026-08-17: "we want to make that average turn over is high
 *  for these". A study board that teaches the shape of a $1.5M/day base is
 *  teaching a pattern he cannot actually trade. */
export const DEFAULT_MIN_TIER = 'ok';

export function parseTier(raw: string | null | undefined): string {
  const v = (raw || '').trim();
  return v || DEFAULT_MIN_TIER;
}

/** A sort the backend actually offers, or the default. The board advertises its
 *  own options, so a key retired server-side degrades instead of 404ing. */
export function parseSort(raw: string | null | undefined,
                          offered?: CmSort[] | null): string {
  const v = (raw || '').trim();
  if (!v) return DEFAULT_SORT;
  if (offered && offered.length) {
    return offered.some((o) => o.key === v) ? v : DEFAULT_SORT;
  }
  return v;
}

export function boardQuery(p: {
  tab: CmTab; limit?: number; days?: number;
  universe?: string; themesFirst?: boolean; pattern?: string | null;
  source?: WinnerSource; minerviniOnly?: boolean; sort?: string;
  minTier?: string;
}): string {
  const q = new URLSearchParams({ tab: p.tab });
  if (p.limit) q.set('limit', String(p.limit));
  if (p.days) q.set('days', String(p.days));
  if (p.tab === 'zones' && p.universe) q.set('universe', p.universe);
  if (p.themesFirst === false) q.set('themes_first', 'false');
  // Sent to the BACKEND on purpose. board._finish ranks and caps before it
  // fetches bars for only the tiles it will show, so sorting in the browser
  // would reorder the ~24 tiles theme priority already chose — "highest
  // volume" would silently mean "highest volume among those 24".
  if (p.sort && p.sort !== DEFAULT_SORT) q.set('sort', p.sort);
  if (p.minTier && p.minTier !== DEFAULT_MIN_TIER) q.set('min_tier', p.minTier);
  // Winners-only params. `pattern` is meaningless for the zone ledger — zone
  // re-entries have no chart-pattern name — so it is dropped there rather than
  // sent and silently ignored.
  if (p.tab === 'winners' && p.source === 'zone') q.set('source', 'zone');
  if (p.tab === 'winners' && p.source !== 'zone' && p.pattern) q.set('pattern', p.pattern);
  if (p.tab === 'winners' && p.source !== 'zone' && p.minerviniOnly) {
    q.set('minervini_only', 'true');
  }
  return q.toString();
}

/* ── chart geometry ───────────────────────────────────────────────────────── */

export type Domain = { lo: number; hi: number };

/** Y-domain over candle highs/lows, widened for nearby bands and lines.
 *
 * The nearness guard is the same idea as zonePlan.chartDomain: a target sitting
 * 40% above the last bar is context, and stretching to it flattens the price
 * action into a streak — which defeats the whole point of a study chart. Only
 * levels within one series-height of the data pull the domain.
 */
export function barDomain(
  bars: CmBar[],
  bands: CmBand[] = [],
  lines: CmLine[] = [],
  padPct = 6,
): Domain {
  const highs = bars.map((b) => b.h).filter((n) => Number.isFinite(n));
  const lows = bars.map((b) => b.l).filter((n) => Number.isFinite(n));
  if (!highs.length || !lows.length) return { lo: 0, hi: 1 };
  let lo = Math.min(...lows);
  let hi = Math.max(...highs);
  const height = hi - lo || 1;

  const stretch = (v: number | null | undefined) => {
    if (v == null || !Number.isFinite(v)) return;
    if (v >= lo - height && v <= hi + height) {
      lo = Math.min(lo, v);
      hi = Math.max(hi, v);
    }
  };
  for (const b of bands) { stretch(b.lo); stretch(b.hi); }
  for (const l of lines) stretch(l.price);

  const pad = ((hi - lo) || hi || 1) * (padPct / 100);
  return { lo: lo - pad, hi: hi + pad };
}

/** Price → SVG y. Inverted (high price = small y). */
export function yFor(price: number, d: Domain, height: number, padY = 8): number {
  const span = d.hi - d.lo || 1e-9;
  const t = (price - d.lo) / span;
  return padY + (1 - t) * (height - 2 * padY);
}

/** Index → SVG x for the centre of bar `i`. */
export function xFor(i: number, n: number, width: number, padR: number): number {
  const w = Math.max(width - padR, 1);
  const bw = w / Math.max(n, 1);
  return i * bw + bw / 2;
}

export function barWidth(n: number, width: number, padR: number): number {
  return Math.max(width - padR, 1) / Math.max(n, 1);
}

/** Clip bands to the visible domain, dropping any that fall outside it, so we
 *  never draw an off-canvas rectangle or a zero-height sliver. */
export function clipBands(bands: CmBand[], d: Domain): CmBand[] {
  const out: CmBand[] = [];
  for (const b of bands) {
    if (!Number.isFinite(b.lo) || !Number.isFinite(b.hi)) continue;
    const lo = Math.max(Math.min(b.lo, b.hi), d.lo);
    const hi = Math.min(Math.max(b.lo, b.hi), d.hi);
    if (hi <= lo) continue;                    // entirely outside the view
    out.push({ ...b, lo, hi });
  }
  return out;
}

const TONE_PRIORITY: Record<CmLineTone, number> = { buy: 3, stop: 3, target: 2, now: 2 };

/** Right-edge labels for the plan lines, de-collided. Reuses zonePlan's
 *  layoutLabels so the two chart surfaces cannot drift apart. */
export function lineLabels(
  lines: CmLine[], d: Domain, height: number, padY = 8,
): LabelItem[] {
  const items: LabelItem[] = lines
    .filter((l) => Number.isFinite(l.price) && l.price >= d.lo && l.price <= d.hi)
    .map((l) => ({
      y: yFor(l.price, d, height, padY),
      text: l.label,
      color: toneColor(l.tone),
      bold: l.tone === 'buy',
      priority: TONE_PRIORITY[l.tone] ?? 2,
    }));
  return layoutLabels(items, { minGap: 10, top: 6, bottom: height - 4, maxShift: 22 });
}

export function toneColor(tone: CmLineTone): string {
  if (tone === 'buy') return 'var(--positive, #22c55e)';
  if (tone === 'stop') return 'var(--negative, #ef4444)';
  if (tone === 'target') return 'var(--gold, #c9a227)';
  return 'var(--text-muted, #94a3b8)';
}

/** Sparse x-axis ticks — first bar of each new month, as {i, label}. A dense
 *  daily axis is unreadable at tile size; month boundaries are what you
 *  actually navigate by. */
export function monthTicks(bars: CmBar[], max = 6): { i: number; label: string }[] {
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const ticks: { i: number; label: string }[] = [];
  let prev = '';
  bars.forEach((b, i) => {
    const mo = (b.t || '').slice(0, 7);
    if (mo && mo !== prev) {
      prev = mo;
      const m = Number(mo.slice(5, 7));
      if (m >= 1 && m <= 12) ticks.push({ i, label: MON[m - 1] });
    }
  });
  if (ticks.length <= max) return ticks;
  const step = Math.ceil(ticks.length / max);
  return ticks.filter((_, i) => i % step === 0);
}

/** Index of a dated marker within the bar window, or -1.
 *  Joined by DATE, never by index — the ledger's indices are offsets into the
 *  full cached frame, not into the window drawn here. */
export function markerIndex(bars: CmBar[], date: string): number {
  const d = (date || '').slice(0, 10);
  if (!d) return -1;
  return bars.findIndex((b) => b.t === d);
}

/* ── formatting ───────────────────────────────────────────────────────────── */

/* Order here mirrors backend THEME_PRIORITY (sepa/universe.py) — Ajay's stated
 * priority, most-wanted first. The board already sorts by it; keeping the same
 * order here means the legend and the tiles tell the same story. */
export const THEME_LABEL: Record<string, string> = {
  space: '🛰 Space',
  quantum: '⚛ Quantum',
  ai_semis: '🔲 AI semis',
  optical: '💡 Optical',
  robotics: '🦾 Robotics',
  ai_infra: '⚡ AI infra',
  nuclear: '☢ Nuclear',
};

export function themeLabel(theme: string | null | undefined): string | null {
  if (!theme) return null;
  return THEME_LABEL[theme] || theme.replace(/_/g, ' ');
}

/** One honest line about a pattern's record.
 *
 * Always states the loss side and the sample size. Never compares patterns to
 * each other — their stop brackets differ ~2x, which is exactly the broken
 * comparison the 2026-07-10 pattern audit found. */
export function recordLine(r: CmPatternRecord | null | undefined): string {
  if (!r || !r.n) return 'no resolved observations yet';
  const pct = r.win_pct == null ? '—' : `${r.win_pct}%`;
  return `${r.wins} hit target · ${r.losses} stopped out · ${pct} of ${r.n}`;
}

/** Small-sample guard. Under this many resolved observations a win rate is a
 *  number, not a finding. */
export const MIN_SAMPLE = 20;

export function isThinSample(n: number | null | undefined): boolean {
  return !n || n < MIN_SAMPLE;
}
