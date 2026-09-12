/* Sorting the 🚀 Explosive Growth board (2026-09-12).
 *
 * Ajay: "sort this by demand intact".
 *
 * The behaviour that decides whether this sort can be trusted is NOT that
 * intact leads — it is that a name with NO zone read never floats to the top
 * of an ascending sort and reads as the worst on the board. Unknown is not a
 * zero.
 */
import { describe, it, expect } from 'vitest';
import {
  DEFAULT_DIR, DEFAULT_SORT, DEMAND_INTACT, DEMAND_OUT, DEMAND_PIERCED,
  SORT_KEYS, arrow, demandRank, initialDir, sortRows, sortValue,
} from './growthSort';
import type { GrowthRowLike } from './growthSort';

const row = (symbol: string, zone: GrowthRowLike['zone'],
             sales = 100, extra: Partial<GrowthRowLike> = {}): GrowthRowLike =>
  ({ symbol, zone, sales_growth_pct: sales, ...extra });

const INTACT = row('HHH', { missing: false, in_band: true, intact: true }, 330.2);
const PIERCED = row('ABC', { missing: false, in_band: true, intact: false }, 900);
const OUT = row('DBRG', { missing: false, in_band: false, intact: null }, 15961.5);
const NOBAND = row('PROP', { missing: true, in_band: false, intact: null }, 627.4);
const FLOOR_UNKNOWN = row('XYZ', { missing: false, in_band: true, intact: null }, 800);

// ────────────────────────────────────────────────────────────── the ladder
describe('demandRank — ordered by distance from the ONE measured gate', () => {
  it('ranks intact above pierced above out', () => {
    expect(demandRank(INTACT.zone)).toBe(DEMAND_INTACT);
    expect(demandRank(PIERCED.zone)).toBe(DEMAND_PIERCED);
    expect(demandRank(OUT.zone)).toBe(DEMAND_OUT);
    expect(DEMAND_INTACT).toBeGreaterThan(DEMAND_PIERCED);
    expect(DEMAND_PIERCED).toBeGreaterThan(DEMAND_OUT);
  });

  it('NEGATIVE: no zone read at all is UNKNOWN, not the bottom rung', () => {
    expect(demandRank(NOBAND.zone)).toBeNull();
    expect(demandRank(undefined)).toBeNull();
  });

  it('NEGATIVE: in a band with an unanswered floor gate is UNKNOWN, not pierced', () => {
    // This is the case that used to render as "in band, pierced" — a fact
    // nobody checked, stated as if it had been.
    expect(demandRank(FLOOR_UNKNOWN.zone)).toBeNull();
    expect(demandRank(FLOOR_UNKNOWN.zone)).not.toBe(DEMAND_PIERCED);
  });
});

// ──────────────────────────────────────────────────────────── the ordering
describe('sortRows — demand', () => {
  const ALL = [OUT, NOBAND, PIERCED, INTACT, FLOOR_UNKNOWN];

  it('puts the intact floors on top — the ask', () => {
    // The two unknowns land last and rank among THEMSELVES on the board's own
    // tiebreak, sales growth desc: XYZ 800 before PROP 627.4.
    expect(sortRows(ALL, 'demand', 'desc').map((r) => r.symbol))
      .toEqual(['HHH', 'ABC', 'DBRG', 'XYZ', 'PROP']);
  });

  it('NEGATIVE: an unknown sorts LAST ASCENDING TOO, never to the top', () => {
    const asc = sortRows(ALL, 'demand', 'asc').map((r) => r.symbol);
    // worst KNOWN state leads...
    expect(asc[0]).toBe('DBRG');
    expect(asc.indexOf('ABC')).toBeLessThan(asc.indexOf('HHH'));
    // ...and both unknowns stay pinned at the bottom in this direction too.
    expect(asc.slice(-2).sort()).toEqual(['PROP', 'XYZ']);
  });

  it('the flip is a true reverse of the KNOWN rows only', () => {
    const known = [OUT, PIERCED, INTACT];
    expect(sortRows(known, 'demand', 'desc').map((r) => r.symbol))
      .toEqual([...sortRows(known, 'demand', 'asc')].reverse().map((r) => r.symbol));
  });

  it('breaks ties on sales growth, so equal-demand rows never shuffle', () => {
    const a = row('AAA', { in_band: true, intact: true }, 50);
    const b = row('BBB', { in_band: true, intact: true }, 500);
    expect(sortRows([a, b], 'demand', 'desc').map((r) => r.symbol)).toEqual(['BBB', 'AAA']);
    // and the tiebreak does NOT flip with the direction — it is the board's
    // own order, not part of the comparison being reversed
    expect(sortRows([a, b], 'demand', 'asc').map((r) => r.symbol)).toEqual(['BBB', 'AAA']);
  });

  it('NEGATIVE: it never sorts the caller’s array in place', () => {
    const orig = [OUT, INTACT];
    const copy = [...orig];
    sortRows(orig, 'demand', 'desc');
    expect(orig).toEqual(copy);
  });
});

// ───────────────────────────────────────────────────────── numeric columns
describe('sortRows — the numeric columns that shipped with it', () => {
  const rows: GrowthRowLike[] = [
    row('A', {}, 100, { market_cap: 7.4e9, price: 148.18 }),
    row('B', {}, 200, { market_cap: null, price: 0.45 }),
    row('C', {}, 300, { market_cap: 2.98e9, price: 15.9 }),
  ];

  it('ranks by the column, biggest first', () => {
    expect(sortRows(rows, 'market_cap', 'desc').map((r) => r.symbol)).toEqual(['A', 'C', 'B']);
  });

  it('NEGATIVE: a blank cap sorts last ASCENDING too — the PROP case', () => {
    // The board's real PROP row has a dash for cap. Scoring a blank as 0 is
    // right descending and puts an unknown at rank 1 ascending.
    expect(sortRows(rows, 'market_cap', 'asc').map((r) => r.symbol)).toEqual(['C', 'A', 'B']);
  });

  it('NEGATIVE: NaN and Infinity count as missing, not as numbers', () => {
    expect(sortValue(row('X', {}, 0, { price: NaN }), 'price').known).toBe(false);
    expect(sortValue(row('X', {}, 0, { price: Infinity }), 'price').known).toBe(false);
    expect(sortValue(row('X', {}, 0, { price: 0 }), 'price')).toEqual({ known: true, value: 0 });
  });

  it('the symbol column reads A→Z', () => {
    expect(sortRows(rows, 'symbol', 'asc').map((r) => r.symbol)).toEqual(['A', 'B', 'C']);
    expect(initialDir('symbol')).toBe('asc');
    expect(initialDir('demand')).toBe('desc');
  });
});

// ──────────────────────────────────────────────────────────────── the head
describe('the header state', () => {
  it('the board OPENS on demand, intact first', () => {
    expect(DEFAULT_SORT).toBe('demand');
    expect(DEFAULT_DIR).toBe('desc');
  });

  it('exactly one column carries an arrow', () => {
    const on = SORT_KEYS.filter((k) => arrow(k, 'demand', 'desc') !== '');
    expect(on).toEqual(['demand']);
    expect(arrow('demand', 'demand', 'desc')).toBe(' ▾');
    expect(arrow('demand', 'demand', 'asc')).toBe(' ▴');
  });

  it('every printed column is sortable and every key is unique', () => {
    expect(new Set(SORT_KEYS).size).toBe(SORT_KEYS.length);
    expect(SORT_KEYS).toContain('demand');
    expect(SORT_KEYS.length).toBe(9);
  });
});
