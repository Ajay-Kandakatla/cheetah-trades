/* 🏆 setup filter helpers (2026-11-22) — pure. Ajay: "also reversal squeeze is mainly what I look for." · "yes please" ·
 * "CLRO another example add all the videos may be click them together" (one row per stock; the filter keeps ROWS on
 * the served `filter_keys`). NEGATIVES: junk options dropped, junk rows dropped, a 0-count pick → all, order kept. */
import { describe, expect, it } from 'vitest';
import {
  RP_SETUP_ALL, RP_WINNERS_SYM_PARAM, rpFilterWinnerRows, rpPickedFilter, rpRowMatches, rpSetupOptions,
  rpWinnerLabelChips, rpWinnersSym, type RpWinnerRow,
} from './replays';

const r = (symbol: string, filter_keys: unknown) => ({ symbol, filter_keys, videos: [] } as any as RpWinnerRow);
const R: RpWinnerRow[] = [r('A', ['reversal_squeeze', 'intraday_vcp']), r('B', ['none']), r('C', []),
  r('D', ['reversal_squeeze'])];

describe('rpSetupOptions', () => {
  it('keeps well-formed served entries in served order', () => {
    const o = [{ key: 'all', label: 'L', count: 3 }, { key: 'reversal_squeeze', label: 'R', count: 0 }];
    expect(rpSetupOptions(o)).toEqual(o);
  });
  it('NEGATIVE: not a list → []; junk entries dropped', () => {
    expect(rpSetupOptions(null)).toEqual([]);
    expect(rpSetupOptions({ key: 'all' })).toEqual([]);
    expect(rpSetupOptions([null, 1, { key: '', label: 'x', count: 1 }, { key: 'k', label: 1, count: 1 },
      { key: 'k', label: 'x', count: NaN }, { key: 'k', label: 'x', count: -1 }, { key: 'k', label: 'x', count: '2' }]))
      .toEqual([]);
  });
});

describe('rpRowMatches / rpFilterWinnerRows (2026-11-22: the filter keeps ROWS)', () => {
  it("'all' passes every row, junk included", () => {
    for (const c of [r('x', null), r('y', ['none']), r('z', 42), null]) expect(rpRowMatches(c, RP_SETUP_ALL)).toBe(true);
    expect(rpFilterWinnerRows(R, RP_SETUP_ALL)).toEqual(R);
  });
  it('🎾 keeps the rows whose served filter_keys hold it; served order kept', () => {
    expect(rpFilterWinnerRows(R, 'reversal_squeeze').map((x) => x.symbol)).toEqual(['A', 'D']);
    expect(rpFilterWinnerRows(R, 'intraday_vcp').map((x) => x.symbol)).toEqual(['A']);
  });
  it('NEGATIVE: a row with no / junk filter_keys never passes a setup key; a card-level setup is never read', () => {
    expect(rpRowMatches(r('C', []), 'none')).toBe(false);
    expect(rpRowMatches(r('J', 'reversal_squeeze'), 'reversal_squeeze')).toBe(false);
    expect(rpRowMatches({ setup: 'reversal_squeeze' } as any, 'reversal_squeeze')).toBe(false);
    expect(rpRowMatches(null, 'none')).toBe(false);
    expect(rpRowMatches(r('B', ['none']), 'reversal_squeeze')).toBe(false);
  });
  it('NEGATIVE: not a list → []; a row with no reel list is dropped; the input is never mutated', () => {
    expect(rpFilterWinnerRows(null, RP_SETUP_ALL)).toEqual([]);
    expect(rpFilterWinnerRows({ rows: R }, RP_SETUP_ALL)).toEqual([]);
    expect(rpFilterWinnerRows([null, 5, { symbol: 'X', filter_keys: [] }], RP_SETUP_ALL)).toEqual([]);
    const before = JSON.stringify(R);
    rpFilterWinnerRows(R, 'none');
    expect(JSON.stringify(R)).toBe(before);
  });
});

describe('rpPickedFilter (review fix d)', () => {
  const opts = [{ key: 'all', label: 'A', count: 3 }, { key: 'reversal_squeeze', label: 'R', count: 2 },
    { key: 'kiss_fly', label: 'K', count: 0 }];
  it('keeps a served key with a count above 0', () => {
    expect(rpPickedFilter(opts, 'reversal_squeeze')).toBe('reversal_squeeze');
    expect(rpPickedFilter(opts, 'all')).toBe('all');
  });
  it('NEGATIVE: a 0-count key, an unknown key or no options → all', () => {
    expect(rpPickedFilter(opts, 'kiss_fly')).toBe(RP_SETUP_ALL);
    expect(rpPickedFilter(opts, 'cup_handle')).toBe(RP_SETUP_ALL);
    expect(rpPickedFilter([], 'reversal_squeeze')).toBe(RP_SETUP_ALL);
  });
});

describe('rpWinnersSym', () => {
  it('reads the sym param upper-cased; absent → empty', () => {
    expect(RP_WINNERS_SYM_PARAM).toBe('sym');
    expect(rpWinnersSym(new URLSearchParams('winners=1&sym=akan'))).toBe('AKAN');
    expect(rpWinnersSym(new URLSearchParams('winners=1&sym=%20CLRO%20'))).toBe('CLRO');
    expect(rpWinnersSym(new URLSearchParams('winners=1'))).toBe('');
  });
});

describe('rpWinnerLabelChips', () => {
  it('served text only; stopped only when the flag is exactly true', () => {
    const c = { setup_text: 'S', setup_class_text: 'C', stopped_before_peak: true, stopped_text: 'X', timing_text: 'T' };
    expect(rpWinnerLabelChips(c)).toEqual({ setup: 'S', cls: 'C', stopped: 'X', timing: 'T', also: [] });
    expect(rpWinnerLabelChips({ ...c, setup_chips_text: ['also A', '', 5 as any] }).also).toEqual(['also A']);
    expect(rpWinnerLabelChips({ ...c, stopped_before_peak: false }).stopped).toBe('');
    expect(rpWinnerLabelChips({ ...c, stopped_before_peak: 'true' as any }).stopped).toBe('');
  });
  it('NEGATIVE: null / non-string served values print nothing', () => {
    expect(rpWinnerLabelChips(null)).toEqual({ setup: '', cls: '', stopped: '', timing: '', also: [] });
    expect(rpWinnerLabelChips({ setup_text: 5 as any, timing_text: null, setup_chips_text: 'x' as any }))
      .toEqual({ setup: '', cls: '', stopped: '', timing: '', also: [] });
  });
});
