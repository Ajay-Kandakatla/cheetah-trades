import { describe, expect, it } from 'vitest';
import {
  HB_ALL_ON, HB_ALL_PARAM, HB_FILTER_KEYS, HB_FILTER_PARAM, HB_MODE_ALL, HB_MODE_ANY, HB_MODE_PARAM,
  HB_OWN_PARAMS, HB_SORT_DROP, HB_SORT_SWING, HB_SORT_VOL, hbFiltersParam, parseHbAll, parseHbFilters, parseHbMode,
  HB_DIR_PARAM, HB_VIEW_PARAM, HB_VIEW_PRICE, HB_VIEW_SALES, hbHeaderNext, parseHbDir, parseHbView,
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
    // 2026-10-14 b: + hb_dir, hb_view (BUILD_SPEC2 §3.0 — the pin predicted to move)
    expect([...HB_OWN_PARAMS]).toEqual(['hb', 'hb_mode', 'hb_all', 'hb_dir', 'hb_view']);
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

/* 2026-10-14 b — header sorts and the Price | Sales view. Ajay 2026-10-14:
 * "Can you add sort function on the headers and also 5 day and 21 days
 * columns ... and also add sales tab make it like hot sector ...". The server
 * orders; this module parses the URL and says what a header tap asks for. */

describe('🎢 hb_dir / hb_view params (2026-10-14 b)', () => {
  it('direction: asc / desc any case and spacing', () => {
    expect(parseHbDir(' ASC')).toBe('asc');
    expect(parseHbDir('Desc ')).toBe('desc');
  });

  it('NEGATIVE: anything else is no direction (the server opens the column in its first)', () => {
    for (const v of ['up', 'down', '', ' ', 'ascending', '1', null, undefined]) {
      expect(parseHbDir(v as string), String(v)).toBeNull();
    }
  });

  it('view: sales only for sales (any case); NEGATIVE: junk / empty / null stay on price', () => {
    expect(parseHbView('Sales')).toBe(HB_VIEW_SALES);
    expect(parseHbView(' SALES ')).toBe('sales');
    for (const v of ['price', 'sale', 'fundamentals', '', null, undefined, '1']) {
      expect(parseHbView(v as string), String(v)).toBe(HB_VIEW_PRICE);
    }
  });

  it('the param names', () => {
    expect(HB_DIR_PARAM).toBe('hb_dir');
    expect(HB_VIEW_PARAM).toBe('hb_view');
    expect(HB_VIEW_PRICE).toBe('price');
    expect(HB_VIEW_SALES).toBe('sales');
  });
});

describe('🎢 hbHeaderNext — what a header tap asks for (K4: desc first, tap again flips)', () => {
  const swing = { sort: 'hb_swing', first: 'desc' };
  const today = { sort: 'hb_drop', first: 'asc' };
  const ret5 = { sort: 'hb_ret_5d', first: 'desc' };
  const board = { sort: 'hb_swing', sort_dir: 'desc' };

  it('a new column opens in its served first direction (dir null = no hb_dir in the URL)', () => {
    expect(hbHeaderNext(ret5, board)).toEqual({ sort: 'hb_ret_5d', dir: null });
    expect(hbHeaderNext(ret5, null)).toEqual({ sort: 'hb_ret_5d', dir: null });
  });

  it('the active column flips; the flip of the flip lands back on its first (dir null)', () => {
    const one = hbHeaderNext(ret5, { sort: 'hb_ret_5d', sort_dir: 'desc' });
    expect(one).toEqual({ sort: 'hb_ret_5d', dir: 'asc' });
    const two = hbHeaderNext(ret5, { sort: 'hb_ret_5d', sort_dir: one!.dir });
    expect(two).toEqual({ sort: 'hb_ret_5d', dir: null });
    expect(hbHeaderNext(swing, board)).toEqual({ sort: 'hb_swing', dir: 'asc' });
    expect(hbHeaderNext(swing, { sort: 'hb_swing', sort_dir: 'asc' })).toEqual({ sort: 'hb_swing', dir: null });
  });

  it("Today's first is asc: a new tap opens it asc, the next tap writes desc", () => {
    expect(hbHeaderNext(today, board)).toEqual({ sort: 'hb_drop', dir: null });
    expect(hbHeaderNext(today, { sort: 'hb_drop', sort_dir: 'asc' })).toEqual({ sort: 'hb_drop', dir: 'desc' });
    expect(hbHeaderNext(today, { sort: 'hb_drop', sort_dir: 'desc' })).toEqual({ sort: 'hb_drop', dir: null });
  });

  it('an unreadable served sort_dir reads as the column\'s first (the server\'s own resolution)', () => {
    expect(hbHeaderNext(ret5, { sort: 'hb_ret_5d', sort_dir: null })).toEqual({ sort: 'hb_ret_5d', dir: 'asc' });
    expect(hbHeaderNext(today, { sort: 'hb_drop', sort_dir: 'junk' })).toEqual({ sort: 'hb_drop', dir: 'desc' });
  });

  it('NEGATIVE: a column with no served sort (or no readable first) is not a sort head', () => {
    expect(hbHeaderNext({ sort: null, first: null }, board)).toBeNull();
    expect(hbHeaderNext({}, board)).toBeNull();
    expect(hbHeaderNext({ sort: '', first: 'desc' }, board)).toBeNull();
    expect(hbHeaderNext({ sort: 'hb_beta', first: null }, board)).toBeNull();
    expect(hbHeaderNext({ sort: 'hb_beta', first: 'sideways' }, board)).toBeNull();
  });
});

describe('🎢 ?raw pin — the FE names equal high_beta_tab.py (2026-10-14 b)', () => {
  const lit = (src: string, name: string): string | null => {
    const m = new RegExp(`^${name} = "([a-z_]+)"`, 'm').exec(src);
    return m ? m[1] : null;
  };

  it('DIR_PARAM / TABLE_VIEW_PARAM / VIEW_PRICE / VIEW_SALES and DIRS', async () => {
    const { default: src } = await import('../../../backend/chart_maps/high_beta_tab.py?raw');
    expect(lit(src, 'DIR_PARAM'), 'DIR_PARAM').toBe(HB_DIR_PARAM);
    expect(lit(src, 'TABLE_VIEW_PARAM'), 'TABLE_VIEW_PARAM').toBe(HB_VIEW_PARAM);
    expect(lit(src, 'VIEW_PRICE'), 'VIEW_PRICE').toBe(HB_VIEW_PRICE);
    expect(lit(src, 'VIEW_SALES'), 'VIEW_SALES').toBe(HB_VIEW_SALES);
    const dirs = /^DIRS = \(([^)]*)\)/m.exec(src);
    expect(dirs, 'DIRS').not.toBeNull();
    const vals = [...dirs![1].matchAll(/"([a-z]+)"/g)].map((x) => x[1]);
    expect([...vals].sort()).toEqual(['asc', 'desc']);
    for (const v of vals) expect(parseHbDir(v), v).toBe(v);
  });

  it('NEGATIVE: the reader returns null on a renamed / absent constant, so the pin fails loudly', () => {
    expect(lit('DIR_PARAMETER = "hb_dir"\n', 'DIR_PARAM')).toBeNull();
    expect(lit('  DIR_PARAM = "hb_dir"\n', 'DIR_PARAM')).toBeNull();
    expect(lit('', 'VIEW_SALES')).toBeNull();
    expect(lit('VIEW_SALES = "sales"\n', 'VIEW_SALES')).toBe('sales');
  });
});
