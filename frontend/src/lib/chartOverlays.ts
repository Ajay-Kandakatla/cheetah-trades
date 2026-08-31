/* chartOverlays — the legend, and which overlay families are hidden.
 *
 * Ajay 2026-08-31: "Chart feel so clumsy can you give me a ledger and some
 * check boxes to toggle these off from the view."
 *
 * One definition of the overlay FAMILIES a chart tile can carry, shared by
 * every surface that draws PatternChart tiles (the Chart Maps grid, the
 * Support tab, the Session tab), so a checkbox means the same thing
 * everywhere. Each entry doubles as the legend: swatch + name + what it is.
 *
 * Pure module — the component stays dumb and the filtering is testable.
 */
import type { CmTile } from './chartMaps';

export type OverlayGroup = {
  key: string;
  label: string;
  /** Matches PatternChart's BAND_FILL so the swatch IS the chart's color. */
  swatch: string;
  hint: string;
  bandKinds?: string[];
  lineTones?: string[];
  /** Case-insensitive LABEL prefixes ("swept 71.80", "support 68.43", ...).
   *  A prefix match beats a tone match: the support tab draws its support
   *  label with tone "buy", and without precedence the Trade-lines checkbox
   *  would swallow it (Ajay 2026-08-31: "I wanna able to toggle these", on a
   *  screenshot of exactly those right-edge labels). */
  linePrefixes?: string[];
};

export const OVERLAY_GROUPS: OverlayGroup[] = [
  { key: 'demand', label: 'Support / demand', swatch: 'var(--positive, #22c55e)',
    hint: 'tested demand bands and pattern bases',
    bandKinds: ['demand', 'base'], linePrefixes: ['support'] },
  { key: 'supply', label: 'Overhead / supply', swatch: 'var(--negative, #ef4444)',
    hint: 'bands of overhead supply',
    bandKinds: ['supply'], linePrefixes: ['overhead'] },
  { key: 'order_block', label: 'Order blocks', swatch: 'var(--accent, #a78bfa)',
    hint: 'last opposing candle before an institutional-sized impulse (SMC, uncited)',
    bandKinds: ['order_block'], linePrefixes: ['order block'] },
  { key: 'fvg', label: 'Fair value gaps', swatch: 'var(--info, #38bdf8)',
    hint: 'unfilled three-bar imbalances',
    bandKinds: ['fvg_demand', 'fvg_supply'], linePrefixes: ['fvg'] },
  { key: 'range', label: 'Ranges', swatch: 'var(--text-muted, #94a3b8)',
    hint: 'opening range / gamma walls — a range has no side',
    bandKinds: ['neutral'], linePrefixes: ['orb'] },
  { key: 'trade', label: 'Trade lines', swatch: 'var(--cm-amber, #d97706)',
    hint: 'BUY / STOP / TARGET prices',
    lineTones: ['buy', 'stop', 'target'] },
  { key: 'structure', label: 'SMC reads', swatch: 'var(--warn, #e8a33d)',
    hint: 'BOS / CHoCH / swept-level lines (uncited convention)',
    linePrefixes: ['bos', 'choch', 'swept'] },
  { key: 'now', label: 'Now line', swatch: 'var(--ink, #e7e7e7)',
    hint: 'the last price marker',
    lineTones: ['now'] },
];

const BY_BAND: Record<string, string> = {};
const BY_TONE: Record<string, string> = {};
const BY_PREFIX: Array<[string, string]> = [];
for (const g of OVERLAY_GROUPS) {
  for (const k of g.bandKinds || []) BY_BAND[k] = g.key;
  for (const t of g.lineTones || []) BY_TONE[t] = g.key;
  for (const p of g.linePrefixes || []) BY_PREFIX.push([p, g.key]);
}

/** Which family a LINE belongs to. Label prefix beats tone — see the type. */
function lineGroup(l: { label?: string; tone?: string }): string | undefined {
  const lab = (l.label || '').toLowerCase();
  for (const [p, key] of BY_PREFIX) {
    if (lab.startsWith(p)) return key;
  }
  return BY_TONE[l.tone || ''];
}

/** Which groups actually appear on this view — a checkbox for an overlay the
 *  board never draws is a control that does nothing. */
export function presentGroups(tiles: Array<Partial<CmTile>>): OverlayGroup[] {
  const seen = new Set<string>();
  for (const t of tiles || []) {
    for (const b of t.bands || []) {
      const g = BY_BAND[b.kind as string];
      if (g) seen.add(g);
    }
    for (const l of t.lines || []) {
      const g = lineGroup(l as any);
      if (g) seen.add(g);
    }
  }
  return OVERLAY_GROUPS.filter((g) => seen.has(g.key));
}

/** The tile with hidden families removed. Identity when nothing is hidden.
 *  Unknown kinds/tones are always KEPT — a new overlay must appear by default,
 *  never vanish because the legend has not heard of it yet. */
export function filterTile<T extends Partial<CmTile>>(tile: T, hidden: Set<string>): T {
  if (!hidden.size || !tile) return tile;
  return {
    ...tile,
    bands: (tile.bands || []).filter((b) => !hidden.has(BY_BAND[b.kind as string] || '')),
    lines: (tile.lines || []).filter((l) => !hidden.has(lineGroup(l as any) || '')),
  };
}

const LS_KEY = 'cm-hidden-overlays';

/** localStorage round-trip, both directions inside try/catch: a blocked or
 *  cleared store must render the default view, never a broken one. */
export function loadHidden(): Set<string> {
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    const legal = new Set(OVERLAY_GROUPS.map((g) => g.key));
    return new Set((Array.isArray(arr) ? arr : []).filter((k) => legal.has(k)));
  } catch {
    return new Set();
  }
}

export function saveHidden(hidden: Set<string>): void {
  try {
    window.localStorage.setItem(LS_KEY, JSON.stringify([...hidden]));
  } catch {
    /* per-viewer convenience only — losing it must cost nothing */
  }
}
