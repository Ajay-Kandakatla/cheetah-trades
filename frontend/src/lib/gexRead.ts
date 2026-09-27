/* 🧲 GEX on Chart Maps — the tile read, the "🧲 Bullish GEX first" order and
 * the batched just-in-time payload (Ajay 2026-09-27).
 *
 * His words are quoted verbatim in the ✨ entry (newFeatures.ts,
 * gex-chart-maps-2026-09-27) and the dated doc
 * (docs/chart_maps/gex_chips_2026_09_27.md).
 *
 * THE READ IS SERVED. backend/chart_maps/gex_read.py decides every bucket
 * (options.gex_history.board_bucket, reused verbatim), every void (a settled
 * expiry, no usable gamma), the strength (net dealer gamma over the stock's
 * 50-day average dollar volume), the group, the sort key and every word of the
 * chips and their hovers. The legend (which group is "no read", and the label
 * of each group) is served too. Nothing in this file names a bucket, rounds a
 * number or compares one against a typed value: a second copy of the rule in
 * TSX is a second engine that drifts the first time the backend moves.
 *
 * UNMEASURED — no study says GEX predicts the next move. The box re-orders the
 * tiles already on screen; it hides, gates, sizes and alerts nothing. The state
 * lives in the URL (`?gex=off` when unticked) and nowhere else; toggling never
 * refetches the board.
 */

/** One read — nightly (the 17:50 ET post-close ledger row) or live (the
 *  just-in-time read, never written to the ledger). Shape = backend §3.3.
 *  `bucket` is one of the served bucket keys, null exactly when `void` is set;
 *  `void` is null, settled or no_gamma. Typed as strings on purpose: this file
 *  never spells a bucket. */
export type GexRead = {
  kind: string;
  bucket: string | null;
  void: string | null;
  regime: string | null;
  spot: number | null;
  flip_strike: number | null;
  put_wall: number | null;
  call_wall: number | null;
  net_gex_dollars: number | null;
  adv_dollars_50: number | null;
  /** SIGNED net / ADV; null when void or either side is missing. */
  strength: number | null;
  expiration_date: string | null;
  days_to_expiry: number | null;
  reliability: string | null;
  as_of: string;
  as_of_text: string;
};

/** One served chip: kind single / close / now / none; tone good / warn / muted. */
export type GexChip = {
  kind: string;
  text: string;
  tone: string;
  title: string;
};

export type GexLiveStatus = 'not_asked' | 'ok' | 'no_options' | 'pending' | 'failed' | 'market_closed';

/** The tile block (`tiles[i].gex`) AND each just-in-time row — the SAME shape. */
export type GexTileRead = {
  symbol: string;
  live_status: GexLiveStatus | string;
  nightly: GexRead | null;
  live: GexRead | null;
  /** 1 or 2 chips, drawn in array order. */
  chips: GexChip[];
  sort: { group: number; key: number | null; source: string | null };
};

export type GexLegendGroup = { group: number; key: string; label: string };
export type GexLegend = { no_read_group: number; groups: GexLegendGroup[] };
export type GexSortOff = { label: string; title: string };
export type GexCounts = Record<string, number>;

/** POST /chart-maps/gex-live — always 200, one row per requested symbol. */
export type GexLivePayload = {
  as_of: string;
  as_of_text: string;
  session: string;
  market_closed: string | null;
  rows: Record<string, GexTileRead>;
  pending: number;
  counts: GexCounts;
  legend: GexLegend;
  scope: string;
  sort_off: GexSortOff | null;
  ttl_sec: number;
  budget_sec: number;
  truncated: number;
  rule: string;
  note: string;
};

/** The one URL key. Default ON; only the OFF value is written. */
export const GEX_PARAM = 'gex';

/** ON unless the URL says exactly `off` — a typo lands on the default. */
export function parseGexParam(v: string | null | undefined): boolean {
  return v !== 'off';
}

/** The value to write for a state; null = delete the key. */
export function gexParam(on: boolean): string | null {
  return on ? null : 'off';
}

const isNum = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);

/** A row the page can draw and sort, or null. Drops a row without a chips
 *  array or a numeric group (an older payload, a stub, a broken build). */
export function sanitizeGexRow(x: unknown): GexTileRead | null {
  if (!x || typeof x !== 'object') return null;
  const r = x as Partial<GexTileRead>;
  if (!Array.isArray(r.chips)) return null;
  if (!r.sort || typeof r.sort !== 'object' || !isNum(r.sort.group)) return null;
  return r as GexTileRead;
}

/** A legend the order can trust, or null (→ served order, no counts). */
export function validLegend(l: unknown): GexLegend | null {
  if (!l || typeof l !== 'object') return null;
  const g = l as Partial<GexLegend>;
  if (!isNum(g.no_read_group) || !Array.isArray(g.groups)) return null;
  return g as GexLegend;
}

/** The read a tile draws: the just-in-time row when it landed (it carries the
 *  nightly read too), else the board's own nightly block. */
export function gexOf(
  tile: { symbol?: string | null; gex?: GexTileRead | null } | null | undefined,
  liveMap: ReadonlyMap<string, GexTileRead> | null | undefined,
): GexTileRead | null {
  if (!tile) return null;
  const sym = String(tile.symbol ?? '').toUpperCase();
  return sanitizeGexRow(liveMap?.get(sym)) ?? sanitizeGexRow(tile.gex) ?? null;
}

/** The served group of a read; a missing or broken read sits in the legend's
 *  no-read group. */
function groupOf(read: GexTileRead | null | undefined, legend: GexLegend): number {
  const r = sanitizeGexRow(read);
  return r ? r.sort.group : legend.no_read_group;
}

/** 🧲 Bullish GEX first. A STABLE sort on the served keys, never a filter:
 *  group ascending, then the served key descending (a null key after every
 *  number), then the tab's own order. OFF, or no served legend → a copy in the
 *  incoming order. The ON board is a permutation of the OFF board. */
export function sortByGex<T>(
  rows: readonly T[],
  readOf: (row: T) => GexTileRead | null | undefined,
  on: boolean,
  legend?: GexLegend | null,
): T[] {
  const all = (rows || []) as readonly T[];
  const lg = validLegend(legend);
  if (!on || !lg) return all.slice();
  const keyed = all.map((row, i) => {
    const r = sanitizeGexRow(readOf(row));
    return { row, i, g: groupOf(r, lg), k: r && isNum(r.sort.key) ? r.sort.key : null };
  });
  keyed.sort((a, b) => {
    const dg = a.g - b.g;
    if (dg) return dg;
    if (a.k !== null && b.k !== null) {
      const dk = b.k - a.k;
      if (dk) return dk;
    } else if (a.k !== null) {
      return -1;
    } else if (b.k !== null) {
      return 1;
    }
    return a.i - b.i;
  });
  return keyed.map((x) => x.row);
}

/** The tally the checkbox prints, in the legend's order with the legend's
 *  labels. A missing read counts under the no-read group. No legend → []. */
export function countGex<T>(
  rows: readonly T[],
  readOf: (row: T) => GexTileRead | null | undefined,
  legend?: GexLegend | null,
): Array<{ key: string; label: string; n: number }> {
  const lg = validLegend(legend);
  if (!lg) return [];
  const known = new Set(lg.groups.map((g) => g.group));
  const n = new Map<number, number>();
  for (const row of rows || []) {
    let g = groupOf(readOf(row), lg);
    if (!known.has(g)) g = lg.no_read_group;
    n.set(g, (n.get(g) ?? 0) + 1);
  }
  return lg.groups.map((g) => ({ key: g.key, label: g.label, n: n.get(g.group) ?? 0 }));
}

const H13 = "🧲 is not wired into this tab yet — waiting on Ajay's answer (H13)";

/** Every Chart Maps tab that is NOT a tile grid, and why 🧲 is not on it. The
 *  contract checks these keys against CM_TABS, so a new non-grid tab has to be
 *  listed here with a reason before it ships. */
export const GEX_EXEMPT: Record<string, string> = {
  support: 'one symbol per view',
  holdings: H13,
  potus: H13,
  signals: H13,
  session: H13,
  ema_frames: H13,
  bonde: H13,
  growth: H13,
  gnt: H13,
  catalysts: H13,
  news: H13,
  hot_sectors: H13,
  patterns: H13,
  hot_pullback: H13,
  overnight: H13,
};
