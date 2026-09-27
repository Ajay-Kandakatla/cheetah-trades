/* 🧲 gexRead — the URL key, the stable served-key sort, the tally and the
 * sanitiser behind "🧲 Bullish GEX first" (Ajay 2026-09-27: "make it sorted by
 * bullish gex please.." → "Checkbox, ON by default").
 *
 * Built on the hand-written §3.3 contract example. Pinned: default ON; the ON
 * order is bullish (key desc) → bullish without a key → mixed in tab order →
 * bearish (key desc: weakest first) → no read; untick restores the served
 * order exactly; nothing is ever hidden; no legend → served order. */
import { describe, expect, it } from 'vitest';
import RAW from '../components/__fixtures__/gex_contract_example_2026_09_27.json?raw';
import {
  GEX_EXEMPT, GEX_PARAM, countGex, gexOf, gexParam, parseGexParam, sanitizeGexRow, sortByGex,
  validLegend, type GexLegend, type GexTileRead,
} from './gexRead';
import { CM_TABS, isBoardTab } from './chartMaps';

type Tile = { symbol: string; gex?: GexTileRead | null };
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const fx = JSON.parse(RAW) as any;
const TILES = fx.board.tiles as unknown as Tile[];
const LEGEND = fx.board.gex_legend as GexLegend;
const LIVE_ROWS = fx.live.rows as unknown as Record<string, GexTileRead>;
const syms = (rows: Tile[]) => rows.map((t) => t.symbol);
const nightly = (t: Tile) => t.gex;
const SERVED = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF', 'GGG', 'HHH', 'III'];

describe('🧲 URL key', () => {
  it('default ON; only the exact "off" turns it off; garbage lands ON', () => {
    expect(GEX_PARAM).toBe('gex');
    expect(parseGexParam(null)).toBe(true);
    expect(parseGexParam(undefined)).toBe(true);
    expect(parseGexParam('off')).toBe(false);
    expect(parseGexParam('0')).toBe(true);
    expect(parseGexParam('false')).toBe(true);
    expect(parseGexParam('OFF')).toBe(true);
  });
  it('gexParam writes only the OFF value', () => {
    expect(gexParam(true)).toBeNull();
    expect(gexParam(false)).toBe('off');
  });
});

describe('🧲 sortByGex', () => {
  it('ON: bullish key desc → bullish null key → mixed → bearish key desc → no read (tab order inside)', () => {
    expect(syms(TILES)).toEqual(SERVED);
    const on = sortByGex(TILES, nightly, true, LEGEND);
    expect(syms(on)).toEqual(['HHH', 'DDD', 'FFF', 'AAA', 'BBB', 'GGG', 'CCC', 'EEE', 'III']);
  });

  it('NEGATIVE: untick restores the exact served order (a copy, not the same array)', () => {
    const off = sortByGex(TILES, nightly, false, LEGEND);
    expect(syms(off)).toEqual(SERVED);
    expect(off).not.toBe(TILES);
  });

  it('NEGATIVE: hides nothing — ON is a permutation of OFF', () => {
    const on = sortByGex(TILES, nightly, true, LEGEND);
    expect(on).toHaveLength(TILES.length);
    expect([...syms(on)].sort()).toEqual([...SERVED].sort());
  });

  it('NEGATIVE: a no-read name never sits above a bearish one; mixed never above bullish', () => {
    const on = sortByGex(TILES, nightly, true, LEGEND);
    const idx = (s: string) => syms(on).indexOf(s);
    for (const nr of ['CCC', 'EEE', 'III']) for (const b of ['BBB', 'GGG']) expect(idx(nr)).toBeGreaterThan(idx(b));
    for (const b of ['HHH', 'DDD', 'FFF']) expect(idx('AAA')).toBeGreaterThan(idx(b));
  });

  it('the settled-void nightly read (EEE) sorts with no read, never bullish', () => {
    const e = TILES.find((t) => t.symbol === 'EEE')!.gex!;
    expect(e.nightly?.void).toBe('settled');
    expect(e.nightly?.bucket).toBeNull();
    expect(e.sort.group).toBe(LEGEND.no_read_group);
  });

  it('ties keep the tab order', () => {
    const same = (sym: string): Tile => ({ symbol: sym, gex: { ...TILES[7].gex!, symbol: sym } });
    const rows = [same('Z1'), same('Z2'), same('Z3')];
    expect(syms(sortByGex(rows, nightly, true, LEGEND))).toEqual(['Z1', 'Z2', 'Z3']);
  });

  it('NEGATIVE: a tile with no gex (older payload) sorts at legend.no_read_group and never throws', () => {
    const rows: Tile[] = [{ symbol: 'OLD' }, ...TILES, { symbol: 'BAD', gex: { chips: 'x' } as unknown as GexTileRead }];
    const on = sortByGex(rows, nightly, true, LEGEND);
    expect(syms(on).slice(0, 6)).toEqual(['HHH', 'DDD', 'FFF', 'AAA', 'BBB', 'GGG']);
    expect(syms(on).slice(6)).toEqual(['OLD', 'CCC', 'EEE', 'III', 'BAD']);
  });

  it('NEGATIVE: no legend (or a broken one) → served order exactly, even ticked', () => {
    expect(syms(sortByGex(TILES, nightly, true, null))).toEqual(SERVED);
    expect(syms(sortByGex(TILES, nightly, true, undefined))).toEqual(SERVED);
    expect(syms(sortByGex(TILES, nightly, true, { groups: [] } as unknown as GexLegend))).toEqual(SERVED);
    expect(validLegend({ no_read_group: 'x', groups: [] })).toBeNull();
  });

  it('the no-read group comes from the SERVED legend, not a typed number', () => {
    // A legend that says group 1 is "no read": a missing read must land in 1.
    const alt: GexLegend = { no_read_group: 1, groups: LEGEND.groups };
    const rows: Tile[] = [{ symbol: 'OLD' }, TILES[1], TILES[7]]; // no read, bearish(2), bullish(0)
    expect(syms(sortByGex(rows, nightly, true, alt))).toEqual(['HHH', 'OLD', 'BBB']);
  });

  it('with the live rows the disagreeing name (DDD) moves to the bearish group', () => {
    const on = sortByGex(TILES, (t) => gexOf(t, new Map(Object.entries(LIVE_ROWS))), true, LEGEND);
    expect(syms(on)).toEqual(['HHH', 'EEE', 'FFF', 'AAA', 'BBB', 'DDD', 'GGG', 'CCC', 'III']);
  });
});

describe('🧲 gexOf / sanitizeGexRow', () => {
  it('prefers the live row, falls back to the tile block, upper-cases the symbol', () => {
    const map = new Map(Object.entries(LIVE_ROWS));
    const ddd = TILES.find((t) => t.symbol === 'DDD')!;
    expect(gexOf(ddd, map)).toBe(LIVE_ROWS.DDD);
    expect(gexOf({ symbol: 'ddd', gex: ddd.gex }, map)).toBe(LIVE_ROWS.DDD);
    expect(gexOf(ddd, new Map())).toBe(ddd.gex);
    expect(gexOf(ddd, null)).toBe(ddd.gex);
  });
  it('NEGATIVE: a broken live row does not shadow a good tile block; nothing → null', () => {
    const ddd = TILES.find((t) => t.symbol === 'DDD')!;
    const bad = new Map([['DDD', { symbol: 'DDD' } as unknown as GexTileRead]]);
    expect(gexOf(ddd, bad)).toBe(ddd.gex);
    expect(gexOf({ symbol: 'X' }, bad)).toBeNull();
    expect(gexOf(null, bad)).toBeNull();
  });
  it('NEGATIVE: sanitizeGexRow drops rows without chips[] or a numeric group', () => {
    expect(sanitizeGexRow(null)).toBeNull();
    expect(sanitizeGexRow({})).toBeNull();
    expect(sanitizeGexRow({ chips: [], sort: { group: '0' } })).toBeNull();
    expect(sanitizeGexRow({ chips: {}, sort: { group: 0 } })).toBeNull();
    expect(sanitizeGexRow(TILES[0].gex)).toBe(TILES[0].gex);
  });
});

describe('🧲 countGex', () => {
  it('counts in legend order with the legend labels', () => {
    expect(countGex(TILES, nightly, LEGEND)).toEqual([
      { key: 'bullish', label: 'bullish', n: 3 }, { key: 'mixed', label: 'mixed', n: 1 },
      { key: 'bearish', label: 'bearish', n: 2 }, { key: 'none', label: 'no read', n: 3 },
    ]);
    // Same totals as the served tally.
    expect(countGex(TILES, nightly, LEGEND).map((c) => c.n))
      .toEqual([fx.board.gex_counts.bullish, fx.board.gex_counts.mixed, fx.board.gex_counts.bearish, fx.board.gex_counts.none]);
  });
  it('NEGATIVE: a legend with other labels prints THOSE labels (nothing typed here)', () => {
    const alt: GexLegend = { no_read_group: 3, groups: LEGEND.groups.map((g) => ({ ...g, label: `L${g.group}` })) };
    expect(countGex(TILES, nightly, alt).map((c) => c.label)).toEqual(['L0', 'L1', 'L2', 'L3']);
  });
  it('NEGATIVE: a missing read counts under no read; no legend → []', () => {
    const c = countGex([{ symbol: 'OLD' } as Tile], nightly, LEGEND);
    expect(c.find((x) => x.key === 'none')!.n).toBe(1);
    expect(countGex(TILES, nightly, null)).toEqual([]);
  });
});

describe('🧲 GEX_EXEMPT', () => {
  it('lists exactly the non-grid Chart Maps tabs, each with a reason', () => {
    const grid = CM_TABS.filter((t) => isBoardTab(t));
    const nonGrid = CM_TABS.filter((t) => !isBoardTab(t)).sort();
    expect(Object.keys(GEX_EXEMPT).sort()).toEqual(nonGrid);
    for (const t of grid) expect(GEX_EXEMPT[t]).toBeUndefined();
    for (const v of Object.values(GEX_EXEMPT)) expect(v.trim().length).toBeGreaterThan(0);
  });
});
