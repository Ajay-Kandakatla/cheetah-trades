/* 🏎️ Dual Momentum filter boxes — the param parser / writer and boardQuery (2026-09-29).
 * Ajay, verbatim: "Can you add AMD raided and near demand zone and near lower
 * Key level filters to dual momentum please". */
import { describe, expect, it } from 'vitest';
import { DM_FILTER_KEYS, DM_FILTER_PARAM, dmFiltersParam, parseDmFilters } from './dmFilters';
import { boardQuery } from './chartMaps';

const arr = (s: Set<string>) => Array.from(s).sort();

describe('parseDmFilters', () => {
  it('known keys, any case / spacing, `,` or `+`, duplicates collapse', () => {
    expect(arr(parseDmFilters('level,AMD, foo'))).toEqual(['amd', 'level']);
    expect(arr(parseDmFilters(' Zone + amd '))).toEqual(['amd', 'zone']);
    expect(arr(parseDmFilters('amd,amd,level,level'))).toEqual(['amd', 'level']);
    expect(arr(parseDmFilters('amd,zone,level'))).toEqual(['amd', 'level', 'zone']);
  });
  it('NEGATIVE: null / empty / unknown-only -> empty', () => {
    for (const v of [null, undefined, '', '   ', 'foo', 'foo,bar', ',,+']) {
      expect(parseDmFilters(v as string | null | undefined).size, String(v)).toBe(0);
    }
    // NEGATIVE: a non-string never throws
    expect(parseDmFilters(7 as unknown as string).size).toBe(0);
  });
});

describe('dmFiltersParam', () => {
  it('canonical order amd,zone,level whatever the input order', () => {
    expect(dmFiltersParam(['level', 'amd'])).toBe('amd,level');
    expect(dmFiltersParam(new Set(['zone', 'level', 'amd']))).toBe('amd,zone,level');
    expect(dmFiltersParam(['LEVEL', ' zone '])).toBe('zone,level');
  });
  it('NEGATIVE: empty or unknown-only -> null (no param)', () => {
    expect(dmFiltersParam([])).toBeNull();
    expect(dmFiltersParam(['foo', 'bar'])).toBeNull();
    expect(dmFiltersParam(new Set<string>())).toBeNull();
  });
  it('round-trips through the parser', () => {
    expect(dmFiltersParam(parseDmFilters('level,zone,amd'))).toBe('amd,zone,level');
  });
});

describe('the keys', () => {
  it('DM_FILTER_KEYS is the server FILTER_KEYS order; the param is `dm`', () => {
    expect([...DM_FILTER_KEYS]).toEqual(['amd', 'zone', 'level']);
    expect(DM_FILTER_PARAM).toBe('dm');
  });
});

describe('boardQuery sends `dm` on the Dual Momentum tab only', () => {
  it('dual_momentum + dmFilters -> dm', () => {
    const q = boardQuery({ tab: 'dual_momentum', dmFilters: 'amd,zone' });
    expect(new URLSearchParams(q).get('dm')).toBe('amd,zone');
  });
  it('NEGATIVE: another tab never carries it', () => {
    for (const tab of ['zones', 'key_levels', 'amd', 'deep_demand'] as const) {
      const q = boardQuery({ tab, dmFilters: 'amd' });
      expect(new URLSearchParams(q).has('dm'), tab).toBe(false);
    }
  });
  it('NEGATIVE: no selection -> no dm', () => {
    expect(new URLSearchParams(boardQuery({ tab: 'dual_momentum' })).has('dm')).toBe(false);
    expect(new URLSearchParams(boardQuery({ tab: 'dual_momentum', dmFilters: '' })).has('dm')).toBe(false);
  });
});
