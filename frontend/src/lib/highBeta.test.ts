import { describe, expect, it } from 'vitest';
import {
  HB_ALL_ON, HB_ALL_PARAM, HB_FILTER_KEYS, HB_FILTER_PARAM, HB_MODE_ALL, HB_MODE_ANY, HB_MODE_PARAM,
  HB_OWN_PARAMS, HB_SORT_DROP, HB_SORT_SWING, HB_SORT_VOL, hbFiltersParam, parseHbAll, parseHbFilters, parseHbMode,
} from './highBeta';
import { HB_SORT_DROP as CM_HB_SORT_DROP, HB_SORT_VOL as CM_HB_SORT_VOL } from './chartMaps';

/* 🎢 High Beta (Ajay 2026-10-14: "give me all 3 categories") — the URL params
 * only. The server decides every pass; this module parses and writes. */

describe('🎢 High Beta params', () => {
  it('the five keys, in the canonical (served) order, and the param names', () => {
    expect([...HB_FILTER_KEYS]).toEqual(['b15', 'b20', 'top20', 'qqq', 'd5']);
    expect(HB_FILTER_PARAM).toBe('hb');
    expect(HB_MODE_PARAM).toBe('hb_mode');
    expect(HB_ALL_PARAM).toBe('hb_all');
    expect(HB_ALL_ON).toBe('1');
    expect([...HB_OWN_PARAMS]).toEqual(['hb', 'hb_mode', 'hb_all']);
  });

  it('the sort keys, re-exported by chartMaps (one definition)', () => {
    expect(HB_SORT_SWING).toBe('hb_swing');
    expect(HB_SORT_DROP).toBe('hb_drop');
    expect(HB_SORT_VOL).toBe('hb_vol');
    expect(CM_HB_SORT_DROP).toBe(HB_SORT_DROP);
    expect(CM_HB_SORT_VOL).toBe(HB_SORT_VOL);
  });

  it('parse: split on , and +, trim, lowercase, known keys only', () => {
    expect([...parseHbFilters('D5, b20+top20')].sort()).toEqual(['b20', 'd5', 'top20']);
    expect([...parseHbFilters(' qqq ')]).toEqual(['qqq']);
  });

  it('NEGATIVE: unknown / empty / null tokens are dropped, never passed on', () => {
    expect(parseHbFilters(null).size).toBe(0);
    expect(parseHbFilters(undefined).size).toBe(0);
    expect(parseHbFilters('').size).toBe(0);
    expect(parseHbFilters('b25,beta,t1,amd,dn10, ,').size).toBe(0);
    // the spec draft's `dn5` is not the served key (DECISIONS K2: `d5`)
    expect(parseHbFilters('dn5').size).toBe(0);
    expect([...parseHbFilters('b15,foo')]).toEqual(['b15']);
  });

  it('serialize: canonical order whatever the click order; null when nothing known', () => {
    expect(hbFiltersParam(['d5', 'qqq', 'b15'])).toBe('b15,qqq,d5');
    expect(hbFiltersParam(new Set(['TOP20', 'b20']))).toBe('b20,top20');
    expect(hbFiltersParam([])).toBeNull();
    expect(hbFiltersParam(['foo', 'res'])).toBeNull();
  });

  it('round-trips: parse(serialize(x)) == x for every subset', () => {
    for (let m = 1; m < 32; m += 1) {
      const sel = HB_FILTER_KEYS.filter((_, i) => m & (1 << i));
      const back = parseHbFilters(hbFiltersParam(sel));
      expect([...back].sort()).toEqual([...sel].sort());
    }
  });

  it('mode: "all" only for all (any case); anything else any', () => {
    expect(parseHbMode('ALL ')).toBe(HB_MODE_ALL);
    for (const v of [null, undefined, '', 'any', 'and', 'every', '1']) expect(parseHbMode(v as string)).toBe(HB_MODE_ANY);
  });

  it('green names: on only for 1 / true; NEGATIVE: anything else stays red-only', () => {
    expect(parseHbAll('1')).toBe(true);
    expect(parseHbAll(' TRUE ')).toBe(true);
    for (const v of [null, undefined, '', '0', 'false', 'yes', 'all', '2']) expect(parseHbAll(v as string), String(v)).toBe(false);
  });
});
