/* 🛡️ Resiliency filter boxes — the param parser / writer and boardQuery (2026-09-30).
 * Ajay, verbatim: "Can you build me a new tab- Resileincy. This is to help me
 * with #1 - Stocks that are not going to by more than 0.5% during a T1 event
 * like FOMC or any others like todays Inflation and GDP track T2s as well. #3
 * - Tape is positive and bullish EOD or Pre market. but volume has to be
 * accounted for. We have all of this data already." */
import { describe, expect, it } from 'vitest';
import {
  RES_FILTER_KEYS, RES_FILTER_PARAM, RES_MODE_ALL, RES_MODE_ANY, RES_MODE_PARAM,
  parseResFilters, parseResMode, resFiltersParam,
} from './resiliencyFilters';
import { DM_MODE_ALL, parseDmMode } from './dmFilters';
import { boardQuery } from './chartMaps';

const arr = (s: Set<string>) => Array.from(s).sort();

describe('parseResFilters', () => {
  it('known keys, any case / spacing, `,` or `+`, duplicates collapse', () => {
    expect(arr(parseResFilters('EOD, t1,foo'))).toEqual(['eod', 't1']);
    expect(arr(parseResFilters(' Pre + T2 '))).toEqual(['pre', 't2']);
    expect(arr(parseResFilters('t1,t1,eod,eod'))).toEqual(['eod', 't1']);
    expect(arr(parseResFilters('t1,t2,eod,pre'))).toEqual(['eod', 'pre', 't1', 't2']);
  });
  it('NEGATIVE: null / empty / unknown-only / DM keys -> empty', () => {
    for (const v of [null, undefined, '', '   ', 'foo', 'amd,zone,level', ',,+', 't3', 'eod1']) {
      expect(parseResFilters(v as string | null | undefined).size, String(v)).toBe(0);
    }
    expect(parseResFilters(7 as unknown as string).size).toBe(0);
  });
});

describe('resFiltersParam', () => {
  it('canonical order t1,t2,eod,pre whatever the input order', () => {
    expect(resFiltersParam(['eod', 't1'])).toBe('t1,eod');
    expect(resFiltersParam(new Set(['pre', 'eod', 't2', 't1']))).toBe('t1,t2,eod,pre');
    expect(resFiltersParam(['PRE', ' t2 '])).toBe('t2,pre');
  });
  it('NEGATIVE: empty or unknown-only -> null (no param)', () => {
    expect(resFiltersParam([])).toBeNull();
    expect(resFiltersParam(['foo', 'amd'])).toBeNull();
    expect(resFiltersParam(new Set<string>())).toBeNull();
  });
  it('round-trips through the parser', () => {
    expect(resFiltersParam(parseResFilters('pre+EOD,t1'))).toBe('t1,eod,pre');
  });
  it('the keys and params are the served names', () => {
    expect([...RES_FILTER_KEYS]).toEqual(['t1', 't2', 'eod', 'pre']);
    expect(RES_FILTER_PARAM).toBe('res');
    expect(RES_MODE_PARAM).toBe('res_mode');
  });
});

describe('parseResMode — the Dual Momentum parser, by import', () => {
  it("'all' in any case / spacing -> all", () => {
    for (const v of ['all', 'ALL', ' All ']) expect(parseResMode(v), v).toBe(RES_MODE_ALL);
    expect(RES_MODE_ALL).toBe(DM_MODE_ALL);
  });
  it('NEGATIVE: absent / blank / junk / non-string -> any; agrees with parseDmMode on every input', () => {
    for (const v of [null, undefined, '', '  ', 'any', 'foo', 'alll', 7]) {
      expect(parseResMode(v as string | null | undefined), String(v)).toBe(RES_MODE_ANY);
      expect(parseResMode(v as string | null | undefined)).toBe(parseDmMode(v as string | null | undefined));
    }
  });
});

describe('boardQuery sends res / res_mode on the Resiliency tab only', () => {
  it('resiliency + boxes -> res; + all -> res_mode=all', () => {
    const q = new URLSearchParams(boardQuery({ tab: 'resiliency', resFilters: 't1,eod', resMode: 'all' }));
    expect(q.get('res')).toBe('t1,eod');
    expect(q.get('res_mode')).toBe('all');
    expect(q.get('tab')).toBe('resiliency');
  });
  it('NEGATIVE: any (or junk) mode never rides; no boxes -> no res', () => {
    for (const m of ['any', 'foo', '', undefined]) {
      const q = new URLSearchParams(boardQuery({ tab: 'resiliency', resFilters: 't1', resMode: m }));
      expect(q.has('res_mode'), String(m)).toBe(false);
    }
    const bare = new URLSearchParams(boardQuery({ tab: 'resiliency' }));
    expect(bare.has('res')).toBe(false);
    expect(bare.has('res_mode')).toBe(false);
  });
  it('NEGATIVE: another tab never carries res / res_mode, and DM params never ride on resiliency', () => {
    for (const tab of ['zones', 'ath', 'dual_momentum'] as const) {
      const q = new URLSearchParams(boardQuery({ tab, resFilters: 't1,eod', resMode: 'all' }));
      expect(q.has('res'), tab).toBe(false);
      expect(q.has('res_mode'), tab).toBe(false);
    }
    const r = new URLSearchParams(boardQuery({ tab: 'resiliency', dmFilters: 'amd', dmMode: 'all' }));
    expect(r.has('dm')).toBe(false);
    expect(r.has('dm_mode')).toBe(false);
  });
});
