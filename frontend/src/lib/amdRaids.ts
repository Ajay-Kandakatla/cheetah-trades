/* amdRaids — every AMD raid on the daily Support tile, past and today's.
 *
 * Ajay 2026-09-24, asked how the AMD chip should behave: "Show all the
 * possible raids, past ones too and todays too."
 *
 * THE BACKEND OWNS EVERY WORD AND EVERY RULE. `chart_maps/board.py
 * ::_attach_amd_raids` walks the ONE detector (`supply_demand/amd.py`) on
 * closed daily bars, adds today's provisional read off the chart's live print,
 * numbers the chains and writes every sentence. This module only:
 *   1. sanitizes the served block (junk in → dropped, never a NaN on screen),
 *   2. places one numbered circle per drawn raid on the chart (geometry only),
 *   3. picks which side of the chip the drill-in panel opens on.
 * It evaluates no raid, no edge and no outcome, and composes no sentence.
 *
 * DISPLAY ONLY: nothing sorts, filters, gates, alerts or buys on these rows.
 * AMD is uncited and MEASURED INVERTED (2026-09-14) — the served `note` says so.
 */
import type { CmBar, CmMarker } from './chartMaps';

export const DIRS = ['bullish', 'bearish'] as const;
export type AmdDir = (typeof DIRS)[number];
export const OUTCOMES = ['marked_up', 'failed', 'live', 'expired'] as const;
export type AmdOutcome = (typeof OUTCOMES)[number];
/** The 🌀 tab's in-flight words, reused for today's provisional read. */
export const STATES = ['sweeping', 'reclaimed', 'holding', 'unknown'] as const;
export type AmdState = (typeof STATES)[number];
/** `1`, `3·2`, `H1`, `H2·3`, or `?` (today beyond the edge — not a raid). */
export const MARK_RE = /^(H?\d{1,3}(·\d{1,2})?|\?)$/;

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** One raid on CLOSED daily bars (amd.find_raids row + the board's fields). */
export type AmdRaid = {
  direction: AmdDir;
  date: string;
  bars_ago: number | null;
  raid_level: number;
  raid_price: number;
  raid_close: number | null;
  depth_pct: number | null;
  vol_ratio: number | null;
  base_lo: number | null;
  base_hi: number | null;
  base_bars: number | null;
  base_date: string;
  base_end_date: string;
  outcome: AmdOutcome;
  outcome_date: string | null;
  outcome_bars_after: number | null;
  markup_bars_left: number | null;
  resweep_of: string | null;
  chain_root: string | null;
  sweep_seq: number | null;
  in_view: boolean;
  closed: true;
  n: number | null;
  mark: string | null;
  text: string;
};

/** Today's provisional read (amd.provisional_raid + the board's fields). */
export type AmdRaidToday = {
  direction: AmdDir;
  state: AmdState;
  closed: false;
  date: string;
  bars_ago: number | null;
  raid_level: number | null;
  base_lo: number | null;
  base_hi: number | null;
  base_bars: number | null;
  base_date: string;
  base_end_date: string;
  price: number;
  day_low: number | null;
  day_high: number | null;
  raid_price: number | null;
  depth_pct: number | null;
  to_edge_pct: number | null;
  resweep_of: string | null;
  chain_root: string | null;
  sweep_seq: number | null;
  price_source: string;
  reason: string | null;
  n: number | null;
  mark: string | null;
  text: string;
};

export type AmdDirCounts = { bullish: number; bearish: number };

export type AmdRaidsChipData = { text: string; tone: 'muted'; title: string };

export type AmdRaidsBlock = {
  raids: AmdRaid[];
  today: AmdRaidToday[];
  draw_dirs: AmdDir[];
  chains_in_view: AmdDirCounts;
  rows_in_view: AmdDirCounts;
  resweeps_in_view: AmdDirCounts;
  chains_off_view: number;
  n_all: number;
  chip: AmdRaidsChipData | null;
  summary: string;
  basis: string;
  verdict_basis_note: string | null;
  note: string;
  through: string;
  frame_from: string;
  cited: boolean;
};

/* ── sanitizer ─────────────────────────────────────────────────────────────── */

const isObj = (x: unknown): x is Record<string, unknown> =>
  x != null && typeof x === 'object' && !Array.isArray(x);
/** A finite number or null. NO string coercion — "139.00" is not a price. */
const num = (v: unknown): number | null =>
  (typeof v === 'number' && Number.isFinite(v) ? v : null);
const pos = (v: unknown): number | null => {
  const n = num(v);
  return n != null && n > 0 ? n : null;
};
const posInt = (v: unknown): number | null => {
  const n = num(v);
  return n != null && Number.isInteger(n) && n > 0 ? n : null;
};
const count = (v: unknown): number => {
  const n = num(v);
  return n != null && Number.isInteger(n) && n >= 0 ? n : 0;
};
const str = (v: unknown): string => (typeof v === 'string' ? v : '');
const strOrNull = (v: unknown): string | null => (typeof v === 'string' && v ? v : null);
const dateOrNull = (v: unknown): string | null =>
  (typeof v === 'string' && DATE_RE.test(v) ? v : null);
const markOf = (v: unknown): string | null =>
  (typeof v === 'string' && MARK_RE.test(v) ? v : null);
const inList = <T extends string>(list: readonly T[], v: unknown): v is T =>
  typeof v === 'string' && (list as readonly string[]).includes(v);
const counts = (v: unknown): AmdDirCounts => {
  const o = isObj(v) ? v : {};
  return { bullish: count(o.bullish), bearish: count(o.bearish) };
};

function cleanRaid(x: unknown): AmdRaid | null {
  if (!isObj(x)) return null;
  if (!inList(DIRS, x.direction)) return null;
  if (typeof x.date !== 'string' || !DATE_RE.test(x.date)) return null;
  const level = pos(x.raid_level);
  const price = pos(x.raid_price);
  if (level == null || price == null) return null;
  if (!inList(OUTCOMES, x.outcome)) return null;
  if (typeof x.text !== 'string' || !x.text.trim()) return null;
  return {
    direction: x.direction,
    date: x.date,
    bars_ago: num(x.bars_ago),
    raid_level: level,
    raid_price: price,
    raid_close: num(x.raid_close),
    depth_pct: num(x.depth_pct),
    vol_ratio: num(x.vol_ratio),
    base_lo: num(x.base_lo),
    base_hi: num(x.base_hi),
    base_bars: num(x.base_bars),
    base_date: str(x.base_date),
    base_end_date: str(x.base_end_date),
    outcome: x.outcome,
    outcome_date: dateOrNull(x.outcome_date),
    outcome_bars_after: num(x.outcome_bars_after),
    markup_bars_left: num(x.markup_bars_left),
    resweep_of: dateOrNull(x.resweep_of),
    chain_root: dateOrNull(x.chain_root),
    sweep_seq: posInt(x.sweep_seq),
    in_view: x.in_view === true,
    closed: true,
    n: posInt(x.n),
    mark: markOf(x.mark),
    text: x.text,
  };
}

function cleanToday(x: unknown): AmdRaidToday | null {
  if (!isObj(x)) return null;
  if (!inList(STATES, x.state)) return null;
  if (!inList(DIRS, x.direction)) return null;
  const price = pos(x.price);
  if (price == null) return null;
  if (typeof x.text !== 'string' || !x.text.trim()) return null;
  return {
    direction: x.direction,
    state: x.state,
    closed: false,
    date: typeof x.date === 'string' && DATE_RE.test(x.date) ? x.date : '',
    bars_ago: num(x.bars_ago),
    raid_level: num(x.raid_level),
    base_lo: num(x.base_lo),
    base_hi: num(x.base_hi),
    base_bars: num(x.base_bars),
    base_date: str(x.base_date),
    base_end_date: str(x.base_end_date),
    price,
    day_low: num(x.day_low),
    day_high: num(x.day_high),
    raid_price: num(x.raid_price),
    depth_pct: num(x.depth_pct),
    to_edge_pct: num(x.to_edge_pct),
    resweep_of: dateOrNull(x.resweep_of),
    chain_root: dateOrNull(x.chain_root),
    sweep_seq: posInt(x.sweep_seq),
    price_source: str(x.price_source),
    reason: strOrNull(x.reason),
    n: posInt(x.n),
    mark: markOf(x.mark),
    text: x.text,
  };
}

/** The served `tile.amd_raids`, or null. Rows that fail a check are DROPPED,
 *  never repaired: a row with no swept edge has nothing true to say. */
export function sanitizeAmdRaids(x: unknown): AmdRaidsBlock | null {
  if (!isObj(x)) return null;
  const raids = (Array.isArray(x.raids) ? x.raids : [])
    .map(cleanRaid).filter((r): r is AmdRaid => r != null);
  const today = (Array.isArray(x.today) ? x.today : [])
    .map(cleanToday).filter((r): r is AmdRaidToday => r != null);
  const draw_dirs = (Array.isArray(x.draw_dirs) ? x.draw_dirs : [])
    .filter((d): d is AmdDir => inList(DIRS, d));
  const c = isObj(x.chip) ? x.chip : null;
  const chip: AmdRaidsChipData | null = c && typeof c.text === 'string' && c.text.trim()
    ? { text: c.text, tone: 'muted', title: str(c.title) }
    : null;
  return {
    raids,
    today,
    draw_dirs,
    chains_in_view: counts(x.chains_in_view),
    rows_in_view: counts(x.rows_in_view),
    resweeps_in_view: counts(x.resweeps_in_view),
    chains_off_view: count(x.chains_off_view),
    n_all: count(x.n_all),
    chip,
    summary: str(x.summary),
    basis: str(x.basis),
    verdict_basis_note: strOrNull(x.verdict_basis_note),
    note: str(x.note),
    through: str(x.through),
    frame_from: str(x.frame_from),
    cited: x.cited === true,
  };
}

/* ── chart geometry ────────────────────────────────────────────────────────── */

/** Circle radius for a one- or two-character mark. */
export const RAID_R = 5.2;
/** Distance from the wick to row 0 — where the single M circle used to sit. */
export const RAID_OFFSET = 8;
/** Distance between stacked rows. */
export const RAID_ROW = 11;
/** Rows tried per side before the other side is tried. */
export const RAID_ROWS = 3;

/** Wider marks ("3·2", "12·3") get a wider circle so the digits stay inside. */
export function raidRadius(mark: string): number {
  const len = (mark || '').length;
  return len <= 2 ? RAID_R : RAID_R + 1.8 * (len - 2);
}

export type RaidSide = 'below' | 'above';
export type Occupied = { i: number; side: RaidSide };

const BELOW_KINDS = new Set(['amd_a', 'amd_x', 'touch_d']);
const ABOVE_KINDS = new Set(['amd_d', 'touch_s']);

const dateIndex = (bars: CmBar[]): Map<string, number> => {
  const m = new Map<string, number>();
  (bars || []).forEach((b, i) => {
    const d = String((b && b.t) || '').slice(0, 10);
    if (d && !m.has(d)) m.set(d, i);
  });
  return m;
};

/** Where the tile's own glyphs already sit (row 0 of their side), joined to
 *  the bars by DATE. A ▲ or an A under a raid's candle pushes the circle to
 *  the next row instead of printing on top of it. */
export function occupiedFromMarkers(markers: CmMarker[], bars: CmBar[]): Occupied[] {
  const idx = dateIndex(bars);
  const out: Occupied[] = [];
  for (const m of markers || []) {
    const kind = (m && m.kind) || '';
    const side: RaidSide | null = BELOW_KINDS.has(kind) ? 'below'
      : ABOVE_KINDS.has(kind) ? 'above' : null;
    if (!side) continue;
    const i = idx.get(String((m && m.date) || '').slice(0, 10));
    if (i == null) continue;
    out.push({ i, side });
  }
  return out;
}

export type AmdRaidMark = {
  i: number;
  mark: string;
  dir: AmdDir;
  live: boolean;
  unsure: boolean;
  text: string;
  side: RaidSide;
  row: number;
  y: number;
  r: number;
};

export type AmdRaidGeom = {
  /** Two circles on the same side and row need at least this many bars apart. */
  minGapBars: number;
  lowY: (i: number) => number;
  highY: (i: number) => number;
  /** The plot's usable y range for a circle CENTRE. A row outside it is
   *  skipped, never clamped — a clamped circle lands on some other candle. */
  top: number;
  bottom: number;
  occupied: Occupied[];
};

/** One numbered circle per drawn raid: in-view closed rows with a mark, plus
 *  today's entries with a mark, in the served `draw_dirs` only. The list and
 *  the circles read the SAME array, so they cannot disagree. A raid with no
 *  free row on either side is left off the chart (the list still carries it). */
export function amdRaidMarks(
  block: AmdRaidsBlock | null, bars: CmBar[], geom: AmdRaidGeom,
): AmdRaidMark[] {
  if (!block || !bars || !bars.length) return [];
  const draw = new Set<string>(block.draw_dirs || []);
  const idx = dateIndex(bars);
  type Cand = { i: number; mark: string; dir: AmdDir; live: boolean; text: string };
  const cands: Cand[] = [];
  for (const r of block.raids || []) {
    if (!r.mark || !r.in_view || !draw.has(r.direction)) continue;
    const i = idx.get(r.date);
    if (i == null) continue;
    cands.push({ i, mark: r.mark, dir: r.direction, live: false, text: r.text });
  }
  for (const e of block.today || []) {
    if (!e.mark || !draw.has(e.direction)) continue;
    const i = idx.get(e.date);
    if (i == null) continue;
    cands.push({ i, mark: e.mark, dir: e.direction, live: true, text: e.text });
  }
  cands.sort((a, b) => a.i - b.i || (a.dir === b.dir ? 0 : a.dir === 'bullish' ? -1 : 1));

  const gap = Math.max(1, Number.isFinite(geom.minGapBars) ? geom.minGapBars : 1);
  const taken: { i: number; side: RaidSide; row: number }[] =
    (geom.occupied || []).map((o) => ({ i: o.i, side: o.side, row: 0 }));
  const out: AmdRaidMark[] = [];
  for (const c of cands) {
    const sides: RaidSide[] = c.dir === 'bullish' ? ['below', 'above'] : ['above', 'below'];
    let placed: AmdRaidMark | null = null;
    for (const side of sides) {
      for (let row = 0; row < RAID_ROWS && !placed; row++) {
        const y = side === 'below'
          ? geom.lowY(c.i) + RAID_OFFSET + row * RAID_ROW
          : geom.highY(c.i) - RAID_OFFSET - row * RAID_ROW;
        if (!Number.isFinite(y) || y > geom.bottom || y < geom.top) continue;
        if (taken.some((t) => t.side === side && t.row === row && Math.abs(t.i - c.i) < gap)) {
          continue;
        }
        placed = {
          i: c.i, mark: c.mark, dir: c.dir, live: c.live, unsure: c.mark === '?',
          text: c.text, side, row, y, r: raidRadius(c.mark),
        };
      }
      if (placed) break;
    }
    if (!placed) continue;
    taken.push({ i: placed.i, side: placed.side, row: placed.row });
    out.push(placed);
  }
  return out;
}

/* ── drill-in panel ────────────────────────────────────────────────────────── */

/** Which way the panel opens from the chip: anchored right when it fits to the
 *  left of the chip's right edge, else anchored left, else a fixed sheet (a
 *  narrow phone). `w` matches the CSS width, min(460px, 92vw). */
export function panelAlign(
  rect: { left: number; right: number }, innerWidth: number,
): 'right' | 'left' | 'fixed' {
  const w = Math.min(460, 0.92 * innerWidth);
  if (rect.right - w >= 8) return 'right';
  if (rect.left + w <= innerWidth - 8) return 'left';
  return 'fixed';
}
