import { describe, it, expect } from 'vitest';
import { alsoOnLinks, newestFirstSeen, tabGlyph, withShowAll } from './growthArrivalsFresh';
import { CM_TABS, TAB_META } from './chartMaps';

/* ✨ Growth arrivals — the pure helpers behind his 2026-10-12 "yes" answers:
 * #7 newestFirstSeen (the StudyNote freshKey), #5 withShowAll (chip hrefs carry
 * the page's own 🎯 override), #8 alsoOnLinks (served per-tab membership →
 * links whose hover says "in the served top N as of …"). */

describe('newestFirstSeen', () => {
  it('returns the max ISO stamp', () => {
    expect(newestFirstSeen([
      { first_seen: '2026-10-05T02:00:00+00:00' },
      { first_seen: '2026-10-12T02:29:05+00:00' },
      { first_seen: '2026-10-11T23:59:59+00:00' },
    ])).toBe('2026-10-12T02:29:05+00:00');
  });

  it('NEGATIVE: ignores null / missing / non-string / empty stamps', () => {
    expect(newestFirstSeen([
      { first_seen: null }, {}, { first_seen: 20261012 as unknown as string },
      { first_seen: '' }, { first_seen: '2026-10-01T00:00:00+00:00' },
    ])).toBe('2026-10-01T00:00:00+00:00');
  });

  it('NEGATIVE: empty / all-invalid / nullish input → null', () => {
    expect(newestFirstSeen([])).toBeNull();
    expect(newestFirstSeen([{ first_seen: null }, {}])).toBeNull();
    expect(newestFirstSeen(null)).toBeNull();
    expect(newestFirstSeen(undefined)).toBeNull();
  });
});

describe('withShowAll', () => {
  it('adds show=all and keeps every other param', () => {
    const q = new URLSearchParams(withShowAll('?tab=growth&focus=PGEN&universe=full').slice(1));
    expect(q.get('show')).toBe('all');
    expect(q.get('tab')).toBe('growth');
    expect(q.get('focus')).toBe('PGEN');
    expect(q.get('universe')).toBe('full');
  });

  it('NEGATIVE: never duplicates show, and overwrites any other show value', () => {
    const once = withShowAll('?tab=growth&show=all');
    expect(new URLSearchParams(once.slice(1)).getAll('show')).toEqual(['all']);
    expect(withShowAll(once)).toBe(once);
    expect(new URLSearchParams(withShowAll('?show=x&tab=zones').slice(1)).getAll('show')).toEqual(['all']);
  });

  it('accepts an href without the leading ? and an empty one', () => {
    expect(withShowAll('tab=growth')).toBe('?tab=growth&show=all');
    expect(withShowAll('')).toBe('?show=all');
  });
});

describe('tabGlyph', () => {
  it('leading emoji, else the whole label', () => {
    expect(tabGlyph('\u{1F680} Breaking')).toBe('\u{1F680}');
    expect(tabGlyph('\u{1F6E1}\u{FE0F} Resiliency')).toBe('\u{1F6E1}\u{FE0F}');
    expect(tabGlyph('Back in Demand')).toBe('Back in Demand');
  });
});

const params = new URLSearchParams('tab=zones&universe=full&pattern=cup');
const entry = (tab: string, extra: Record<string, unknown> = {}) => ({
  tab, built_at: '2026-10-12T14:05:33+00:00', source_as_of: null,
  ttl_name: null, limit: 80, stale: null, ...extra,
});

describe('alsoOnLinks', () => {
  it('orders by CM_TABS, labels from TAB_META, href = tabSearch without focus', () => {
    const links = alsoOnLinks({
      symbol: 'PGEN',
      also_on: [entry('bonde'), entry('amd'), entry('zones')],
    }, params);
    expect(links.map((l) => l.tab)).toEqual(
      ['zones', 'amd', 'bonde'].sort((a, b) => CM_TABS.indexOf(a as never) - CM_TABS.indexOf(b as never)),
    );
    for (const l of links) {
      expect(l.label).toBe(TAB_META[l.tab].label);
      const q = new URLSearchParams(l.href.slice(1));
      expect(q.get('tab')).toBe(l.tab);
      expect(q.get('universe')).toBe('full');
      expect(q.has('focus')).toBe(false);
      expect(q.has('pattern')).toBe(false);
    }
  });

  it('[C8] title: "in the served top {limit} as of" the source stamp when served', () => {
    const [l] = alsoOnLinks({ symbol: 'PGEN', also_on: [entry('ath', {
      source_as_of: '2026-10-12T09:41:07-04:00', built_at: '2026-10-12T14:05:33+00:00',
    })] }, params);
    expect(l.title).toBe(`${TAB_META.ath.label} · in the served top 80 as of 2026-10-12 09:41`);
  });

  it('"as of" falls back to built_at when no source stamp', () => {
    const [l] = alsoOnLinks({ symbol: 'PGEN', also_on: [entry('zones')] }, params);
    expect(l.title).toBe(`${TAB_META.zones.label} · in the served top 80 as of 2026-10-12 14:05`);
  });

  it('NEGATIVE: no served limit → "in the served list", never a typed number', () => {
    const [l] = alsoOnLinks({ symbol: 'PGEN', also_on: [entry('bonde', { limit: null })] }, params);
    expect(l.title).toContain('in the served list');
    expect(l.title).not.toMatch(/top \d/);
  });

  it('stale clause only when the served stale === true, naming the served TTL constant', () => {
    const [s] = alsoOnLinks({ symbol: 'X', also_on: [entry('ath', {
      stale: true, ttl_name: 'chart_maps.ath_tab.MEMO_TTL_SEC',
    })] }, params);
    expect(s.stale).toBe(true);
    expect(s.title).toContain("stale: older than this tab's cache window (chart_maps.ath_tab.MEMO_TTL_SEC)");
    for (const v of [false, null, undefined, 'true', 1]) {
      const [n] = alsoOnLinks({ symbol: 'X', also_on: [entry('ath', { stale: v, ttl_name: 'T' })] }, params);
      expect(n.stale).toBe(false);
      expect(n.title).not.toContain('stale');
    }
  });

  it('NEGATIVE: drops growth, supply, unknown tabs and duplicates', () => {
    const links = alsoOnLinks({ symbol: 'X', also_on: [
      entry('growth'), entry('supply'), entry('nope'), entry('zones'), entry('zones'),
    ] }, params);
    expect(links.map((l) => l.tab)).toEqual(['zones']);
  });

  it.each([
    ['absent', undefined],
    ['null', null],
    ['an object', { zones: true }],
    ['a string', 'zones'],
    ['empty', []],
    ['junk entries', [null, 1, 'zones', {}, { tab: 7 }, { tab: '' }]],
  ])('NEGATIVE: also_on %s → no links', (_n, also_on) => {
    expect(alsoOnLinks({ symbol: 'X', also_on }, params)).toEqual([]);
  });

  it('NEGATIVE: never mutates the live params', () => {
    const p = new URLSearchParams('tab=zones&pattern=cup');
    alsoOnLinks({ symbol: 'X', also_on: [entry('amd')] }, p);
    expect(p.toString()).toBe('tab=zones&pattern=cup');
  });
});
