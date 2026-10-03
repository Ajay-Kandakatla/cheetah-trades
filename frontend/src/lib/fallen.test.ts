/* 📉 Down 40%+ — the three pure helpers (2026-10-02).
 *
 * Ajay 2026-10-02: "Can you build me a tab in chart maps about stocks that
 * dropped more than 40% lowers from like app loving company as an example
 * whcih si 60% low." The depth steps and the sorts are SERVED; these helpers
 * only read them. Negatives carry the weight: a malformed board must never
 * send a depth, and junk entries never become a button. */
import { describe, expect, it } from 'vitest';
import { depthToSend, servedDepths, servedSortKeys } from './fallen';

const DEPTHS = [
  { key: '40', label: '≥40%', on: true, default: true },
  { key: '50', label: '≥50%', on: false, default: false },
  { key: '60', label: '≥60%', on: false, default: false },
  { key: '70', label: '≥70%', on: false, default: false },
];
const board = (depths: unknown = DEPTHS) => ({ state: 'ready', header: 'H', depths });

describe('servedDepths', () => {
  it('returns the served steps in served order, on/default as served', () => {
    expect(servedDepths(board())).toEqual(DEPTHS);
  });

  it('NEGATIVE: a malformed board or depths list → []', () => {
    for (const b of [null, undefined, 7, 'x', [], [board()], { depths: 'x' }, { depths: { a: 1 } }, {}]) {
      expect(servedDepths(b), JSON.stringify(b)).toEqual([]);
    }
  });

  it('NEGATIVE: junk entries (no key, blank label, numbers, arrays) are dropped; truthy-but-not-true flags read false', () => {
    const got = servedDepths(board([
      null, 7, ['40'], { key: '', label: 'x' }, { key: '50' }, { key: 60, label: '≥60%' },
      { key: '70', label: '   ' }, { key: '50', label: '≥50%', on: 'yes', default: 1 },
    ]));
    expect(got).toEqual([{ key: '50', label: '≥50%', on: false, default: false }]);
  });
});

describe('depthToSend', () => {
  it('the served default step → null (the URL stays clean); any other served step → its key', () => {
    expect(depthToSend(board(), '40')).toBeNull();
    expect(depthToSend(board(), '50')).toBe('50');
    expect(depthToSend(board(), '60')).toBe('60');
    expect(depthToSend(board(), '70')).toBe('70');
  });

  it('follows the SERVED default, never a typed one', () => {
    const moved = DEPTHS.map((d) => ({ ...d, default: d.key === '50', on: d.key === '50' }));
    expect(depthToSend(board(moved), '50')).toBeNull();
    expect(depthToSend(board(moved), '40')).toBe('40');
  });

  it('NEGATIVE: a step the server does not offer is never sent ("45", "30", "", null, a number)', () => {
    for (const k of ['45', '30', '', '  ', null, undefined, 60, '40.5', 'abc']) {
      expect(depthToSend(board(), k), String(k)).toBeNull();
    }
  });

  it('NEGATIVE: a malformed board never sends a depth', () => {
    for (const b of [null, undefined, [], 'x', { depths: null }, board([{ key: '60' }])]) {
      expect(depthToSend(b, '60'), JSON.stringify(b)).toBeNull();
    }
  });
});

describe('servedSortKeys', () => {
  it('the served keys in served order', () => {
    expect(servedSortKeys([
      { key: 'default', label: 'a' }, { key: 'fallen_depth', label: 'b' }, { key: 'fallen_sales', label: 'c' },
      { key: 'market_cap', label: 'd' }, { key: 'market_cap_asc', label: 'e' },
    ])).toEqual(['default', 'fallen_depth', 'fallen_sales', 'market_cap', 'market_cap_asc']);
  });

  it('NEGATIVE: ignores junk entries and non-arrays', () => {
    expect(servedSortKeys([null, 7, 'default', { key: 'x' }, { label: 'y' }, { key: '', label: 'z' },
      { key: 3, label: 'n' }, { key: 'fallen_depth', label: 'ok' }])).toEqual(['fallen_depth']);
    for (const v of [null, undefined, 'x', { key: 'a', label: 'b' }]) expect(servedSortKeys(v)).toEqual([]);
  });
});
