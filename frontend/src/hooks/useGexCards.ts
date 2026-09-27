/* useGexCards — 🧲 on the five Chart Maps chart-card tabs (Ajay 2026-09-27:
 * "Got on add it to all tabs now please" / "In chartmaps").
 *
 * Holdings, POTUS, Signals, Session and 9 EMA W/M draw the same chart card as
 * the tile grids but run their own fetchers, so their cards carry no nightly
 * `gex` block. The ONE just-in-time request (useGexLive) is the read here: every
 * served row carries the nightly read too, and off-hours it is the nightly read
 * alone (live_status market_closed). Nothing is decided in this file — the
 * group, key, chip words and legend are served (chart_maps/gex_read.py), and
 * the order is lib/gexRead.sortByGex, the grid tabs' own function.
 *
 *   - `control` absent (a standalone mount such as /signal-lab) → no request,
 *     no chip, the rows come back in their own order;
 *   - `tab` is the board's OWN key, a constant — a board is unmounted on a tab
 *     switch, so its request can never carry another tab's names (the same
 *     guarantee ChartMaps.tsx gets from `gexForThisTab`);
 *   - a failed request keeps the last good answer (useGexLive's rule), so the
 *     nightly chips stay on screen and the box says "live read failed";
 *   - no answer yet, or no legend → the tab's own order exactly;
 *   - ONE request reads at most BOARD_LIMIT names (the server's LIMIT_MAX, the
 *     same per-tab cap as the nightly coverage). A tab with more (Session serves
 *     ~99, backstop 140) asks for its FIRST BOARD_LIMIT in its OWN served order
 *     — useGexLive sorts what it sends, so cutting after it would drop names by
 *     their place in the alphabet. The rest get no read, sort with the no-read
 *     group, and `truncated` says how many (GexToggle shows it).
 *
 * UNMEASURED. It re-orders only; it hides, gates, sizes and alerts nothing.
 */
import { useMemo } from 'react';
import { useGexLive, type GexLiveState } from './useGexLive';
import { BOARD_LIMIT } from '../lib/chartMaps';
import {
  countGex, gexOf, sortByGex,
  type GexCardTab, type GexControl, type GexLegend, type GexSortOff, type GexTileRead,
} from '../lib/gexRead';

const NONE: readonly string[] = [];

export type GexCards = {
  /** A control was passed — this mount is a Chart Maps tab. */
  enabled: boolean;
  /** The box as ticked (false when not enabled). */
  on: boolean;
  live: GexLiveState;
  legend: GexLegend | null;
  sortOff: GexSortOff | null;
  /** The served read for one symbol, or null (never a guess). */
  readOf: (symbol: string | null | undefined) => GexTileRead | null;
  /** 🧲 Bullish GEX first over any rows, stable; OFF / no legend → a copy. */
  order: <T>(rows: readonly T[], symbolOf: (row: T) => string | null | undefined) => T[];
  /** The box's tally over the symbols on screen, legend order and labels. */
  countOf: (symbols: readonly (string | null | undefined)[]) => Array<{ key: string; label: string; n: number }>;
  /** Distinct names past the first BOARD_LIMIT — never asked for, no read. */
  truncated: number;
};

/** Upper-cased, trimmed, de-duplicated, in the CALLER's order (first wins). */
function servedOrder(symbols: readonly string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const s of symbols) {
    const t = (s ?? '').trim().toUpperCase();
    if (t && !seen.has(t)) { seen.add(t); out.push(t); }
  }
  return out;
}

export function useGexCards(symbols: readonly string[], tab: GexCardTab,
                            control?: GexControl | null, refreshKey?: unknown): GexCards {
  const enabled = Boolean(control);
  const joined = symbols.join(',');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const uniq = useMemo(() => servedOrder(symbols), [joined]);
  const asked = useMemo(() => uniq.slice(0, BOARD_LIMIT), [uniq]);
  const truncated = enabled ? uniq.length - asked.length : 0;
  const live = useGexLive(enabled ? asked : NONE, refreshKey, tab);
  const map = live.map;
  const legend = enabled ? (live.payload?.legend ?? null) : null;
  const sortOff = enabled ? (live.payload?.sort_off ?? null) : null;
  const on = enabled && Boolean(control?.on);

  const fns = useMemo(() => {
    const readOf = (symbol: string | null | undefined): GexTileRead | null =>
      (enabled ? gexOf({ symbol: symbol ?? '' }, map) : null);
    const order = <T,>(rows: readonly T[], symbolOf: (row: T) => string | null | undefined): T[] =>
      sortByGex(rows, (r) => readOf(symbolOf(r)), on && !sortOff, legend);
    const countOf = (syms: readonly (string | null | undefined)[]) =>
      countGex(syms, (s) => readOf(s), legend);
    return { readOf, order, countOf };
  }, [enabled, map, on, sortOff, legend]);

  return { enabled, on, live, legend, sortOff, truncated, ...fns };
}
