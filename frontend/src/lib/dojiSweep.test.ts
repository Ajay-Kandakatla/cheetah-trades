/* lib/dojiSweep — the 🕯️ Doji Sweep param helpers (2026-10-16).
 *
 * Ajay 2026-10-16, verbatim: "create me a new tab for Doji candle after a
 * sweep. For any stocks after a down trend. May be from all chart maps
 * especially on the 60% 70% down stocks"; K3 "Yes, any read; chips narrow".
 *
 * Negatives carry the weight: junk tokens, an empty selection, a body step the
 * server never served, a malformed board — each must leave the URL clean
 * rather than send something the server would read as a different view. */
import { describe, expect, it } from 'vitest';
import {
  DJ_BODY_PARAM, DJ_FILTER_KEYS, DJ_FILTER_PARAM, DJ_OWN_PARAMS, DJ_SORT_ATH, DJ_SORT_TEST,
  djBodyToSend, djFiltersParam, parseDjFilters,
} from './dojiSweep';

/* The served body block shape (doji_sweep_tab.body_block): 5 is the default. */
const board = (on: string) => ({
  body: {
    param: 'dj_body', pct: Number(on),
    steps: [
      { key: '5', label: 'B5', title: 'T5', on: on === '5', default: true },
      { key: '10', label: 'B10', title: 'T10', on: on === '10', default: false },
    ],
  },
});

describe('dojiSweep constants', () => {
  it('the params, chip keys and sort keys equal the backend names', () => {
    expect(DJ_FILTER_PARAM).toBe('dj');
    expect(DJ_BODY_PARAM).toBe('dj_body');
    expect([...DJ_FILTER_KEYS]).toEqual(['w52_40', 'w52_60', 'w52_70', 'ath_60', 'mas', 'reclaimed']);
    expect(DJ_SORT_TEST).toBe('doji_test');
    expect(DJ_SORT_ATH).toBe('doji_ath');
    expect([...DJ_OWN_PARAMS]).toEqual([DJ_FILTER_PARAM, DJ_BODY_PARAM]);
  });
});

describe('parseDjFilters / djFiltersParam', () => {
  it('splits on , and +, trims, lowercases, keeps known keys only', () => {
    expect([...parseDjFilters(' W52_60 + reclaimed,mas ')].sort()).toEqual(['mas', 'reclaimed', 'w52_60']);
  });

  it('serialises in the canonical DJ_FILTER_KEYS order whatever the click order', () => {
    expect(djFiltersParam(['reclaimed', 'w52_40', 'ath_60'])).toBe('w52_40,ath_60,reclaimed');
    expect(djFiltersParam(parseDjFilters('mas+w52_70'))).toBe('w52_70,mas');
  });

  it('NEGATIVE: junk tokens are dropped, never sent', () => {
    expect([...parseDjFilters('junk,w52_50,b15,,  ,mas')]).toEqual(['mas']);
    expect(djFiltersParam(['junk', 'hb', 'b20'])).toBeNull();
  });

  it('NEGATIVE: empty / null / undefined / a non-string → empty set and null param', () => {
    for (const v of ['', '   ', null, undefined]) expect(parseDjFilters(v).size).toBe(0);
    expect(parseDjFilters(42 as unknown as string).size).toBe(0);
    expect(djFiltersParam([])).toBeNull();
    expect(djFiltersParam(new Set<string>())).toBeNull();
  });

  it('round-trips: parse(serialise(x)) is x for every chip', () => {
    for (const k of DJ_FILTER_KEYS) expect([...parseDjFilters(djFiltersParam([k]))]).toEqual([k]);
  });
});

describe('djBodyToSend', () => {
  it('the served default step → null (delete the param)', () => {
    expect(djBodyToSend(board('10'), '5')).toBeNull();
    expect(djBodyToSend(board('5'), '5')).toBeNull();
  });

  it('a served non-default step → its key', () => {
    expect(djBodyToSend(board('5'), '10')).toBe('10');
  });

  it('NEGATIVE: a step the server never served → null (never sent)', () => {
    for (const k of ['7', '15', ' 10 ', '', 'x']) expect(djBodyToSend(board('5'), k), k).toBeNull();
  });

  it('NEGATIVE: a malformed / absent board → null', () => {
    const bad: unknown[] = [null, undefined, 'x', [], {}, { body: null }, { body: 'x' }, { body: { steps: 'x' } },
      { body: { steps: [null, 'x', { key: 10, default: false }] } }];
    for (const b of bad) expect(djBodyToSend(b, '10')).toBeNull();
    expect(djBodyToSend(board('5'), null as unknown as string)).toBeNull();
  });
});
