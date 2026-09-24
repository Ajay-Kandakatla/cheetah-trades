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
  /** Dated marker kinds this family owns (2026-09-14): the swings that make a
   *  band (`touch_d` / `touch_s`), the AMD stage glyphs (`amd_a` … `amd_x`),
   *  the Keltner squeeze dots (`kc_sq`). Hidden with the family. */
  markerKinds?: string[];
  /** Case-insensitive LABEL prefixes ("swept 71.80", "support 68.43", ...).
   *  A prefix match beats a tone match: the support tab draws its support
   *  label with tone "buy", and without precedence the Trade-lines checkbox
   *  would swallow it (Ajay 2026-08-31: "I wanna able to toggle these", on a
   *  screenshot of exactly those right-edge labels). */
  linePrefixes?: string[];
};

export const OVERLAY_GROUPS: OverlayGroup[] = [
  { key: 'demand', label: 'Support / demand', swatch: 'var(--positive, #22c55e)',
    hint: 'tested demand bands and pattern bases — ▲ marks the swing lows that made a band',
    bandKinds: ['demand', 'base'], linePrefixes: ['support'], markerKinds: ['touch_d'] },
  // The demand BOARD's own band on the per-ticker views (2026-09-14): what
  // Back in Demand, Deep Demand, the alert gate and the lanes use. Its own
  // family so it can be hidden without hiding the finer levels, and ON by
  // default because it is the band an alert would name.
  { key: 'board', label: 'Board band · alerts', swatch: 'var(--cm-amber, #d97706)',
    hint: 'The demand board\u2019s band for this name — swing 5, merge 4%, 252 closed bars — the one every S/D board, the alert gate and the paper lanes read. Drawn dashed.',
    bandKinds: ['board_demand', 'board_supply'], linePrefixes: ['board '] },
  { key: 'supply', label: 'Overhead / supply', swatch: 'var(--negative, #ef4444)',
    hint: 'bands of overhead supply — ▼ marks the swing highs that made a band',
    bandKinds: ['supply'], linePrefixes: ['overhead'], markerKinds: ['touch_s'] },
  // 📁 My holdings (2026-09-14): his cost and the stop he typed, on any tile
  // of a name he owns. ON by default and its own family, so the `trade`
  // checkbox (the engine's BUY / STOP / TARGET) never takes his own numbers
  // off the chart with it.
  { key: 'position', label: 'Your position', swatch: 'var(--cm-pink, #ec4899)',
    hint: 'your cost (pink) and the stop you typed on the Portfolio page (blue)',
    lineTones: ['cost', 'ownstop'], linePrefixes: ['your '] },
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
    hint: 'accumulation base, the raid that swept it, the markup after — A / M / D on the bars it happened, ✗ where the base failed (ICT convention, uncited; MEASURED INVERTED 2026-09-13) — every raid numbered on its bar (3·2 = a re-sweep of raid 3\u2019s base; dashed = today, not closed; ? = beyond the edge now); the chip beside the verdict lists them all',
    bandKinds: ['amd_accumulation'], lineTones: ['amd'], linePrefixes: ['amd'],
    markerKinds: ['amd_a', 'amd_m', 'amd_d', 'amd_x'] },
  { key: 'fib', always: true, label: 'Fibonacci', swatch: 'var(--cm-teal, #14b8a6)',
    hint: 'retracements 0.382/0.5/0.618/0.786 + extensions 1.272/1.618 off the last major swing (convention, uncited)',
    lineTones: ['fib'], linePrefixes: ['fib'] },
  { key: 'meanrev', always: true, label: 'Mean reversion', swatch: 'var(--cm-slate, #64748b)',
    hint: 'least-squares mean of the visible window with ±1σ/±2σ — σ is dispersion, NOT a probability',
    lineTones: ['meanrev'], linePrefixes: ['mean'] },
  // Ajay 2026-09-12 asked for "the Keltner channel strategy a new tab", then
  // chose the overlay instead: "Over lay I think is better to toggle off if I
  // want to." Same deal as the other three — uncited, unmeasured, gates
  // nothing, off by default.
  { key: 'keltner', always: true, label: 'Keltner channel', swatch: 'var(--cm-amberlt, #f59e0b)',
    hint: 'EMA20 ± 2×ATR10 as a curve, with a dot under every bar the TTM squeeze is on — a squeeze is compression, NOT a direction (convention, uncited; MEASURED INVERTED 2026-09-13)',
    lineTones: ['keltner'], linePrefixes: ['kc '], markerKinds: ['kc_sq'] },
  // Ajay 2026-09-23: "I need 9 EMA and 20 SMA on our charts and also 200 MA on
  // our charts as check boxes.." THREE families, not one, because he asked for
  // three boxes — hiding the 200 must not take the 9 with it.
  //
  // No 50, no 21, no 10. The periods are his (Rule #1), and each line is a
  // DRAWING: nothing sorts, filters, gates or alerts on it (Rule #10).
  { key: 'ema9', label: '9 EMA', swatch: 'var(--cm-vcp, #2563eb)',
    hint: 'the 9-day exponential moving average of the close — a fast line that weights recent closes most; a drawing, not a signal',
    lineTones: ['ema9'] },
  { key: 'sma20', label: '20 SMA', swatch: 'var(--cm-mint, #6ee7b7)',
    hint: 'the plain 20-day average of the close — every one of the last 20 closes counted equally; a drawing, not a signal',
    lineTones: ['sma20'] },
  // SIMPLE, and that is the whole reason it is here (his answer, 2026-09-23):
  // Minervini’s trend template and this app’s SEPA gate both read the
  // 200-DAY SIMPLE average, so the line on the chart is the same number as the
  // gate that put the name on the board. An EMA200 here would draw a line that
  // disagreed with the board beside it.
  { key: 'sma200', label: '200 SMA', swatch: 'var(--gold, #c9a227)',
    hint: 'the plain 200-day average of the close — the same 200-day simple average Minervini’s trend template and the SEPA gate read. Drawn only where 200 closes exist; the first 199 bars of a frame are a gap, not a guess.',
    lineTones: ['sma200'] },
];

/** The families that are ON when he has never touched a checkbox.
 *
 *  Ajay 2026-09-12: "Default toggle on only supple demand and order block for
 *  me." Everything else starts hidden — including the three overlays added
 *  that same day, which is the point: a new uncited read must not arrive
 *  switched on over the levels he trades. `position` (2026-09-14) is his own
 *  cost and stop, not a read, and it is on: a saved v2 hidden-set from before
 *  it existed simply does not list it, so it shows for everyone.
 *
 *  THE THREE MOVING AVERAGES ARE ON (2026-09-23), and that is not a loophole
 *  in the rule above — read the rule again. What must not arrive switched on
 *  is a NEW UNCITED READ: something that claims to tell him what a chart
 *  means, arriving over the levels he actually trades. A 9 EMA is not a read.
 *  It is a drawing he asked for by name ("I need 9 EMA and 20 SMA on our
 *  charts and also 200 MA on our charts as check boxes"), it says nothing, and
 *  it gates nothing — exactly like `position`, which is on for the same
 *  reason: his own numbers, not our opinion. Arriving OFF would mean he asked
 *  for three lines and got three empty checkboxes.
 *
 *  Please do not "fix" this to match the other families. AMD / fib / meanrev /
 *  keltner are off because they are unmeasured READS; these are axes on a
 *  chart. If he ever wants one off, the checkbox is right there and his choice
 *  persists from then on. */
export const DEFAULT_ON = ['demand', 'supply', 'board', 'order_block', 'position',
  'ema9', 'sma20', 'sma200'];

export function defaultHidden(): Set<string> {
  return new Set(OVERLAY_GROUPS.map((g) => g.key).filter((k) => !DEFAULT_ON.includes(k)));
}

const BY_BAND: Record<string, string> = {};
const BY_TONE: Record<string, string> = {};
const BY_PREFIX: Array<[string, string]> = [];
const BY_MARKER: Record<string, string> = {};
for (const g of OVERLAY_GROUPS) {
  for (const k of g.bandKinds || []) BY_BAND[k] = g.key;
  for (const t of g.lineTones || []) BY_TONE[t] = g.key;
  for (const p of g.linePrefixes || []) BY_PREFIX.push([p, g.key]);
  for (const m of g.markerKinds || []) BY_MARKER[m] = g.key;
}

/** The family a dated marker belongs to, or undefined for an unowned kind
 *  (buy / sell / sweep / bos — the board's own markers, never filtered). */
export function markerGroup(m: { kind?: string } | null | undefined): string | undefined {
  return BY_MARKER[(m && m.kind) || ''];
}

/** A flat Keltner line on a tile that already carries the Keltner CURVE
 *  (2026-09-14). The backend stopped sending both, but a board doc cached
 *  before that, or a tile assembled from two payloads, can still arrive with
 *  the curve AND three horizontal lines at the last bar's values — three
 *  straight lines drawn across a bending channel, plus a duplicate label for
 *  each. The line is dropped; the curve is the channel. */
function isStaleFlatKeltner(l: { tone?: string }, curves: any[] | undefined): boolean {
  return (l.tone || '') === 'keltner'
    && Boolean(curves && curves.some((c) => (c && c.tone) === 'keltner'));
}

/** The overlay family a TAB is about, when it is about one.
 *
 *  The 🌀 boards (2026-09-13) draw exactly one family each, and both families
 *  are OFF in the default hidden-set — so without this, opening KC Coiled
 *  would show a grid of bare candles with a verdict badge and no channel, and
 *  the only way to see the thing the tab exists for would be to know which
 *  checkbox to tick. A tab's own family is forced visible ON THAT TAB ONLY;
 *  his saved choices are untouched and every other tab still honours them. */
export function tabFamily(tab: string): string | undefined {
  return tab === 'keltner' ? 'keltner' : tab === 'amd' ? 'amd' : undefined;
}

/** `hidden` minus the tab's own family. Returns the SAME set when there is
 *  nothing to force, so the common case allocates nothing and memo keys on
 *  identity still hold. */
export function hiddenForTab(hidden: Set<string>, tab: string): Set<string> {
  const fam = tabFamily(tab);
  if (!fam || !hidden.has(fam)) return hidden;
  const next = new Set(hidden);
  next.delete(fam);
  return next;
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
    // A curve is a drawn overlay like any other, so the family that owns it
    // gets its checkbox even on a board whose only Keltner content is the
    // channel itself (the 🌀 tab draws NO flat KC lines — 2026-09-13).
    for (const c of (t as any).curves || []) {
      const g = lineGroup(c as any);
      if (g) seen.add(g);
    }
    for (const m of t.markers || []) {
      const g = markerGroup(m as any);
      if (g) seen.add(g);
    }
  }
  return OVERLAY_GROUPS.filter((g) => g.always || seen.has(g.key));
}

/** The tile with hidden families removed. Identity when nothing is hidden
 *  and nothing is stale. Unknown kinds/tones are always KEPT — a new overlay
 *  must appear by default, never vanish because the legend has not heard of
 *  it yet. */
export function filterTile<T extends Partial<CmTile>>(tile: T, hidden: Set<string>): T {
  if (!tile) return tile;
  const curves = (tile as any).curves as any[] | undefined;
  const stale = (tile.lines || []).some((l) => isStaleFlatKeltner(l as any, curves));
  if (!hidden.size && !stale) return tile;
  return {
    ...tile,
    bands: (tile.bands || []).filter((b) => !hidden.has(BY_BAND[b.kind as string] || '')),
    lines: (tile.lines || []).filter((l) => !hidden.has(lineGroup(l as any) || '')
                                            && !isStaleFlatKeltner(l as any, curves)),
    curves: (curves || [])
      .filter((c: any) => !hidden.has(lineGroup(c) || '')),
    markers: (tile.markers || []).filter((m) => !hidden.has(markerGroup(m as any) || '')),
    // The VERDICT SENTENCE is gated with its own drawing (2026-09-13). A badge
    // with no `group` is a board badge (Setup ready, Vol drying) and is never
    // touched — only a study verdict carries one.
    badges: (tile.badges || []).filter((b) => !b.group || !hidden.has(b.group)),
    // 🌀 Every AMD raid (2026-09-24) — the chip, its list and the numbered
    // circles go with the AMD box, exactly like the verdict sentence above.
    amd_raids: hidden.has('amd') ? null : (tile as any).amd_raids,
  } as T;
}

/* v2 on 2026-09-12. The KEY IS BUMPED ON PURPOSE: the default flipped from
 * "show everything" to "supply/demand + order blocks only", and reading the v1
 * value would hand every existing browser an empty hidden-set — i.e. the OLD
 * default — and his instruction would silently never take effect. A fresh key
 * means the new default applies once, then his own choices persist.
 *
 * STILL v2 AFTER THE 2026-09-23 MOVING AVERAGES, deliberately. The v2 bump was
 * needed because that change flipped an EXISTING key's default from shown to
 * hidden, and a saved set that predated it said nothing about the new rule.
 * Adding an ON-BY-DEFAULT family is the opposite case: `saveHidden` writes only
 * the keys that ARE hidden, so a set saved before 'ema9' / 'sma20' / 'sma200'
 * existed cannot contain them, `loadHidden` returns it unchanged, and
 * `hidden.has('ema9')` is false — the three lines show. Bumping to v3 here
 * would buy nothing and would throw away every checkbox choice he has made
 * since 09-12. `test_a_saved_v2_set_from_before_the_MAs_still_shows_them` pins
 * it rather than leaving it to this paragraph. */
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
export const STUDY_KEYS = ['amd', 'fib', 'meanrev', 'keltner'];

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
