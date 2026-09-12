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
  /** Render this family's checkbox even when the payload carries none of it.
   *  The three study families are fetched ONLY when one of them is on, so a
   *  purely data-driven legend would never show the switch that turns them
   *  on — a control you cannot reach because it is off. */
  always?: boolean;
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
  // Ajay 2026-09-12: "I wanna be able to toggle AMD ... and Fibonacci" and
  // "Also mean reversion please". All three are UNCITED and UNMEASURED, and
  // all three gate nothing — which is why each gets its OWN family rather than
  // being folded into `trade` or `demand`. An unmeasured read must never share
  // a checkbox with the levels he actually trades.
  { key: 'amd', always: true, label: 'AMD phases', swatch: 'var(--cm-violet, #8b5cf6)',
    hint: 'accumulation base, the raid that swept it, the markup after (ICT convention, uncited, unmeasured)',
    bandKinds: ['amd_accumulation'], lineTones: ['amd'], linePrefixes: ['amd'] },
  { key: 'fib', always: true, label: 'Fibonacci', swatch: 'var(--cm-teal, #14b8a6)',
    hint: 'retracements 0.382/0.5/0.618/0.786 + extensions 1.272/1.618 off the last major swing (convention, uncited)',
    lineTones: ['fib'], linePrefixes: ['fib'] },
  { key: 'meanrev', always: true, label: 'Mean reversion', swatch: 'var(--cm-slate, #64748b)',
    hint: 'least-squares mean of the visible window with ±1σ/±2σ — σ is dispersion, NOT a probability',
    lineTones: ['meanrev'], linePrefixes: ['mean'] },
];

/** The families that are ON when he has never touched a checkbox.
 *
 *  Ajay 2026-09-12: "Default toggle on only supple demand and order block for
 *  me." Everything else starts hidden — including the three overlays added
 *  that same day, which is the point: a new uncited read must not arrive
 *  switched on over the levels he trades. */
export const DEFAULT_ON = ['demand', 'supply', 'order_block'];

export function defaultHidden(): Set<string> {
  return new Set(OVERLAY_GROUPS.map((g) => g.key).filter((k) => !DEFAULT_ON.includes(k)));
}

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
  return OVERLAY_GROUPS.filter((g) => g.always || seen.has(g.key));
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

/* v2 on 2026-09-12. The KEY IS BUMPED ON PURPOSE: the default flipped from
 * "show everything" to "supply/demand + order blocks only", and reading the v1
 * value would hand every existing browser an empty hidden-set — i.e. the OLD
 * default — and his instruction would silently never take effect. A fresh key
 * means the new default applies once, then his own choices persist. */
const LS_KEY = 'cm-hidden-overlays-v2';

/** localStorage round-trip, both directions inside try/catch: a blocked or
 *  cleared store must render the DEFAULT view, never a broken one and never
 *  the everything-on view the default replaced. */
export function loadHidden(): Set<string> {
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return defaultHidden();
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return defaultHidden();
    const legal = new Set(OVERLAY_GROUPS.map((g) => g.key));
    return new Set(arr.filter((k) => legal.has(k)));
  } catch {
    return defaultHidden();
  }
}

export function saveHidden(hidden: Set<string>): void {
  try {
    window.localStorage.setItem(LS_KEY, JSON.stringify([...hidden]));
  } catch {
    /* per-viewer convenience only — losing it must cost nothing */
  }
}

/** The three uncited study families. The board fetches them only while at
 *  least one is visible, so a default view costs nothing to draw. */
export const STUDY_KEYS = ['amd', 'fib', 'meanrev'];

export function studiesWanted(hidden: Set<string>): boolean {
  return STUDY_KEYS.some((k) => !hidden.has(k));
}

/** Fibonacci draws on the EXPANDED chart only — Ajay 2026-09-12 picked
 *  "Expanded chart only, not every grid tile", because six fib lines on a
 *  small tile is noise. The family stays in the payload either way; this is a
 *  display rule, not a data one. */
export function filterForGrid<T extends { lines?: any[] }>(tile: T, expanded: boolean): T {
  if (expanded || !tile || !tile.lines?.length) return tile;
  return { ...tile, lines: tile.lines.filter((l) => (l?.tone || '') !== 'fib') };
}
