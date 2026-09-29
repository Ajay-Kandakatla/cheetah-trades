/* 🔥 Hottest multi-column sort — the pure rules (2026-09-28).
 * Ajay: "can you help me with multi column sort". */
import { describe, expect, it } from 'vitest';
import {
  HS_DEFAULT_SORT, HS_MAX_SORT_KEYS, defaultDirFor, isDefaultSort, nextSortState,
  samePlan, shownThenBy, sortBasis, sortMark, thenByParam,
} from './hottestSort';
import type { HsSortState } from './hottestSort';
import { arrow, HS_COLS } from '../components/HottestSectors';

const S = (sort: string, dir: 'desc' | 'asc', thenBy: HsSortState['thenBy'] = []): HsSortState =>
  ({ sort, dir, thenBy });

describe('nextSortState — plain click is today\'s rule', () => {
  it('a new key opens single, at its default direction', () => {
    expect(nextSortState(S('rel_5d', 'desc'), 'q_eps_yoy', false)).toEqual(S('q_eps_yoy', 'desc'));
  });
  it('the same key flips', () => {
    expect(nextSortState(S('rel_5d', 'desc'), 'rel_5d', false)).toEqual(S('rel_5d', 'asc'));
    expect(nextSortState(S('rel_5d', 'asc'), 'rel_5d', false)).toEqual(S('rel_5d', 'desc'));
  });
  it('Next ER opens ascending — who reports soonest', () => {
    expect(defaultDirFor('next_earnings')).toBe('asc');
    expect(defaultDirFor('eq_score')).toBe('desc');
    expect(nextSortState(S('rel_5d', 'desc'), 'next_earnings', false)).toEqual(S('next_earnings', 'asc'));
  });
  it('NEGATIVE: a plain click clears the tie-breaks', () => {
    const s = S('eq_score', 'desc', [{ key: 'q_eps_yoy', dir: 'desc' }]);
    expect(nextSortState(s, 'rel_21d', false).thenBy).toEqual([]);
    expect(nextSortState(s, 'eq_score', false)).toEqual(S('eq_score', 'asc'));
    // NEGATIVE: a plain click on a tie-break column makes it the ONLY key
    expect(nextSortState(s, 'q_eps_yoy', false)).toEqual(S('q_eps_yoy', 'desc'));
  });
});

describe('nextSortState — additive (shift / ⌘ / ctrl)', () => {
  it('appends, then flips, then removes (desc-default key)', () => {
    const a = nextSortState(S('eq_score', 'desc'), 'q_eps_yoy', true);
    expect(a).toEqual(S('eq_score', 'desc', [{ key: 'q_eps_yoy', dir: 'desc' }]));
    const b = nextSortState(a, 'q_eps_yoy', true);
    expect(b.thenBy).toEqual([{ key: 'q_eps_yoy', dir: 'asc' }]);
    const c = nextSortState(b, 'q_eps_yoy', true);
    expect(c.thenBy).toEqual([]);
    expect(c.sort).toBe('eq_score');
  });
  it('the asc-default cycle for Next ER: asc → desc → removed', () => {
    const a = nextSortState(S('eq_score', 'desc'), 'next_earnings', true);
    expect(a.thenBy).toEqual([{ key: 'next_earnings', dir: 'asc' }]);
    const b = nextSortState(a, 'next_earnings', true);
    expect(b.thenBy).toEqual([{ key: 'next_earnings', dir: 'desc' }]);
    expect(nextSortState(b, 'next_earnings', true).thenBy).toEqual([]);
  });
  it('additive on the primary flips it and keeps the tie-breaks', () => {
    const s = S('eq_score', 'desc', [{ key: 'q_eps_yoy', dir: 'desc' }]);
    expect(nextSortState(s, 'eq_score', true)).toEqual(
      S('eq_score', 'asc', [{ key: 'q_eps_yoy', dir: 'desc' }]));
  });
  it('NEGATIVE: at the cap the SAME object comes back (no refetch)', () => {
    const s = S('eq_score', 'desc', [{ key: 'q_eps_yoy', dir: 'desc' }, { key: 'net_margin', dir: 'desc' }]);
    expect(nextSortState(s, 'sales_yoy', true)).toBe(s);
    // but a key already in the plan still cycles at the cap
    expect(nextSortState(s, 'net_margin', true)).not.toBe(s);
  });
  it('NEGATIVE: never exceeds the max, whatever the max is', () => {
    let s = S('rel_5d', 'desc');
    for (const k of ['q_eps_yoy', 'net_margin', 'sales_yoy', 'eq_score', 'rel_21d']) {
      s = nextSortState(s, k, true);
      expect(1 + s.thenBy.length).toBeLessThanOrEqual(HS_MAX_SORT_KEYS);
    }
    let t = S('rel_5d', 'desc');
    for (const k of ['q_eps_yoy', 'net_margin']) t = nextSortState(t, k, true, 2);
    expect(t.thenBy).toEqual([{ key: 'q_eps_yoy', dir: 'desc' }]);
  });
});

describe('thenByParam', () => {
  it('NEGATIVE: a single sort sends no then_by at all', () => {
    expect(thenByParam([])).toBe('');
  });
  it('encodes key:dir pairs exactly', () => {
    expect(thenByParam([{ key: 'q_eps_yoy', dir: 'desc' }])).toBe('&then_by=q_eps_yoy%3Adesc');
    expect(thenByParam([{ key: 'q_eps_yoy', dir: 'desc' }, { key: 'net_margin', dir: 'asc' }]))
      .toBe('&then_by=q_eps_yoy%3Adesc%2Cnet_margin%3Aasc');
  });
});

describe('shownThenBy — the SERVED tie-breaks only', () => {
  it('reads what the server applied', () => {
    expect(shownThenBy({ sorted_then_by: [{ key: 'q_eps_yoy', dir: 'asc' }] }))
      .toEqual([{ key: 'q_eps_yoy', dir: 'asc' }]);
  });
  it('NEGATIVE: absent → [] (never the client state)', () => {
    expect(shownThenBy({})).toEqual([]);
    expect(shownThenBy(null)).toEqual([]);
    expect(shownThenBy({ sorted_then_by: 'q_eps_yoy:desc' })).toEqual([]);
  });
  it('NEGATIVE: malformed entries are dropped', () => {
    expect(shownThenBy({ sorted_then_by: [
      { key: 'q_eps_yoy', dir: 'sideways' }, { key: 7, dir: 'desc' }, null, 'net_margin',
      { key: '', dir: 'asc' }, { key: 'net_margin', dir: 'asc' },
    ] })).toEqual([{ key: 'net_margin', dir: 'asc' }]);
  });
});

describe('sortBasis — settled follows the server, in flight follows the request', () => {
  const state = S('eq_score', 'asc', [{ key: 'q_eps_yoy', dir: 'desc' }]);
  it('settled → served dir + served tie-breaks', () => {
    expect(sortBasis('eq_score', state,
      { sorted_dir: 'desc', sorted_then_by: [{ key: 'net_margin', dir: 'asc' }] }, false))
      .toEqual(S('eq_score', 'desc', [{ key: 'net_margin', dir: 'asc' }]));
  });
  it('NEGATIVE: settled with an empty served list while state asks for one → none', () => {
    expect(sortBasis('eq_score', state, { sorted_dir: 'asc', sorted_then_by: [] }, false).thenBy)
      .toEqual([]);
  });
  it('loading → the request in flight', () => {
    expect(sortBasis('eq_score', state, { sorted_dir: 'desc', sorted_then_by: [] }, true))
      .toEqual(state);
  });
  it('NEGATIVE: an unknown served dir falls back to state', () => {
    expect(sortBasis('eq_score', state, { sorted_dir: 'sideways' }, false).dir).toBe('asc');
  });
  it('NEGATIVE: no payload → the state', () => {
    expect(sortBasis('eq_score', state, null, false)).toEqual(state);
  });
  it('no served sorted_by → the primary is the `shown` argument (the pinned shownSortKey rule)', () => {
    expect(sortBasis('rel_5d', S('pre_1d', 'desc'), { sorted_dir: 'desc' }, false).sort).toBe('rel_5d');
  });
  it('settled → the SERVED primary wins over state (a failed click leaves the old board)', () => {
    expect(sortBasis('eq_score', S('eq_score', 'desc'),
      { sorted_by: 'rel_5d', sorted_dir: 'asc', sorted_then_by: [{ key: 'q_eps_yoy', dir: 'desc' }] },
      false)).toEqual(S('rel_5d', 'asc', [{ key: 'q_eps_yoy', dir: 'desc' }]));
  });
  it('NEGATIVE: in flight the request primary shows even when the payload says otherwise', () => {
    expect(sortBasis('eq_score', S('eq_score', 'desc'), { sorted_by: 'rel_5d' }, true).sort)
      .toBe('eq_score');
  });
  it('NEGATIVE: an empty / non-string served sorted_by falls back to `shown`', () => {
    expect(sortBasis('eq_score', S('eq_score', 'desc'), { sorted_by: '' }, false).sort).toBe('eq_score');
    expect(sortBasis('eq_score', S('eq_score', 'desc'), { sorted_by: 7 }, false).sort).toBe('eq_score');
  });
});

describe('sortMark', () => {
  it('single key: byte-identical to the old arrow() for every column and dir', () => {
    for (const c of HS_COLS) {
      for (const dir of ['desc', 'asc'] as const) {
        expect(sortMark(c.key, 'rel_5d', dir, [])).toBe(arrow(c.key === 'rel_5d', dir));
        expect(sortMark(c.key, c.key, dir, [])).toBe(arrow(true, dir));
      }
    }
  });
  it('multi: priority numbers with their own directions', () => {
    const then = [{ key: 'q_eps_yoy', dir: 'asc' as const }, { key: 'net_margin', dir: 'desc' as const }];
    expect(sortMark('eq_score', 'eq_score', 'desc', then)).toBe(' 1▼');
    expect(sortMark('q_eps_yoy', 'eq_score', 'desc', then)).toBe(' 2▲');
    expect(sortMark('net_margin', 'eq_score', 'desc', then)).toBe(' 3▼');
    // NEGATIVE: a column outside the plan carries nothing
    expect(sortMark('sales_yoy', 'eq_score', 'desc', then)).toBe('');
  });
});

describe('isDefaultSort', () => {
  it('is 5 days, high → low, no tie-breaks — nothing else', () => {
    expect(HS_DEFAULT_SORT).toBe('rel_5d');
    expect(isDefaultSort(S('rel_5d', 'desc'))).toBe(true);
    expect(isDefaultSort(S('rel_5d', 'asc'))).toBe(false);
    expect(isDefaultSort(S('rel_21d', 'desc'))).toBe(false);
    expect(isDefaultSort(S('rel_5d', 'desc', [{ key: 'q_eps_yoy', dir: 'desc' }]))).toBe(false);
  });
});

describe('samePlan', () => {
  it('equal by value, tie-break order included', () => {
    const a = S('rel_5d', 'asc', [{ key: 'q_eps_yoy', dir: 'desc' }]);
    expect(samePlan(a, S('rel_5d', 'asc', [{ key: 'q_eps_yoy', dir: 'desc' }]))).toBe(true);
  });
  it('NEGATIVE: a different dir, key, tie-break dir, order or length is not the same plan', () => {
    const a = S('rel_5d', 'asc', [{ key: 'q_eps_yoy', dir: 'desc' }, { key: 'net_margin', dir: 'desc' }]);
    expect(samePlan(a, S('rel_5d', 'desc', a.thenBy))).toBe(false);
    expect(samePlan(a, S('rel_21d', 'asc', a.thenBy))).toBe(false);
    expect(samePlan(a, S('rel_5d', 'asc', [a.thenBy[1], a.thenBy[0]]))).toBe(false);
    expect(samePlan(a, S('rel_5d', 'asc', [{ key: 'q_eps_yoy', dir: 'asc' }, a.thenBy[1]]))).toBe(false);
    expect(samePlan(a, S('rel_5d', 'asc', [a.thenBy[0]]))).toBe(false);
  });
});
