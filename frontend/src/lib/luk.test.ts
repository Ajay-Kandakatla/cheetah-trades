import { describe, expect, it } from 'vitest';
import {
  LUK_BASE, LUK_REFRESH_FALLBACK_MS, LUK_SPAN_PARAM, LUK_SUB_PARAM, LUK_TAB, LUK_TAPE_PATH,
  lukChartTile, lukHref, lukLegendRows, lukMark, lukQuery, lukRefreshMs, lukScreenCols, lukSpan, lukText, parseLukSub,
  type LukScreen, type LukTile,
} from './luk';

/* 🥇 Luk's FE plumbing (2026-11-01, luk spec §3.13). Ajay: "look at other winners of US stocks champion ship and pic the
 * next best one like Gajjala. Implement their strategy please if they have online resources." The parsers, the hrefs,
 * the GET query (sub / span / focus ONLY), the served cadence and the tile adapter — with NEGATIVES. */

const SERVED = [{ key: 'pullback_reversal' }, { key: 'premarket' }, { key: 'track_record' }];

describe('luk — the route names', () => {
  it('tab, base, params and the tape path', () => {
    expect(LUK_TAB).toBe('luk');
    expect(LUK_BASE).toBe('/chart-maps/luk');
    expect(LUK_SUB_PARAM).toBe('sub');
    expect(LUK_SPAN_PARAM).toBe('span');
    expect(LUK_TAPE_PATH).toBe('/chart-maps/luk/entry-tape');
  });
  it('NEGATIVE: never a 🚩 route', () => {
    expect(LUK_BASE).not.toMatch(/gajjala/);
    expect(LUK_TAPE_PATH).not.toMatch(/gajjala/);
  });
});

describe('parseLukSub', () => {
  it('a served key passes (trimmed, lower-cased)', () => {
    expect(parseLukSub(' Premarket ', SERVED)).toBe('premarket');
    expect(parseLukSub('track_record', SERVED)).toBe('track_record');
  });
  it('before a board lands, any well-formed key rides (the server coerces an unknown one)', () => {
    expect(parseLukSub('leader', null)).toBe('leader');
    expect(parseLukSub('leader', [])).toBe('leader');
  });
  it('NEGATIVE: a key the server did not serve, a blank and a malformed key are null', () => {
    expect(parseLukSub('leader', SERVED)).toBeNull();
    expect(parseLukSub('', SERVED)).toBeNull();
    expect(parseLukSub(null)).toBeNull();
    expect(parseLukSub('../x', null)).toBeNull();
    expect(parseLukSub('a'.repeat(41), null)).toBeNull();
    expect(parseLukSub('<script>', null)).toBeNull();
  });
});

describe('lukHref / lukQuery', () => {
  it('lukHref names the tab, the sub and the focus', () => {
    expect(lukHref('premarket')).toBe('/chart-maps?tab=luk&sub=premarket');
    expect(lukHref('pullback_reversal', 'NVDA')).toBe('/chart-maps?tab=luk&sub=pullback_reversal&focus=NVDA');
  });
  it('NEGATIVE: lukHref carries no span (a sub click drops the 🏁 day picker)', () => {
    expect(new URLSearchParams(lukHref('track_record').split('?')[1]).has('span')).toBe(false);
  });
  it('lukQuery carries sub / span / focus only', () => {
    expect(lukQuery({ sub: 'track_record', span: '5d', focus: 'AAPL' })).toBe('sub=track_record&span=5d&focus=AAPL');
    expect(lukQuery({})).toBe('');
  });
  it('NEGATIVE: blanks are dropped and nothing else rides', () => {
    const q = lukQuery({ sub: ' ', span: '', focus: null, ...({ universe: 'full', tf: '5m' } as any) });
    expect(q).toBe('');
  });
});

describe('lukRefreshMs', () => {
  it('the served refresh_sec, in ms', () => {
    expect(lukRefreshMs({ session: { refresh_sec: 300 } })).toBe(300_000);
  });
  it('NEGATIVE: absent / zero / junk → the 60 s fallback (spec §3.13)', () => {
    expect(LUK_REFRESH_FALLBACK_MS).toBe(60_000);
    for (const b of [null, undefined, {}, { session: {} }, { session: { refresh_sec: 0 } }, { session: { refresh_sec: -5 } },
      { session: { refresh_sec: 'x' } }, { session: { refresh_sec: Number.NaN } }]) {
      expect(lukRefreshMs(b)).toBe(60_000);
    }
  });
});

describe('small helpers', () => {
  it('lukText prints a served string, never "undefined"/"null"/blank', () => {
    expect(lukText('x')).toBe('x');
    for (const v of ['', '  ', null, undefined, 3, {}]) expect(lukText(v)).toBeNull();
  });
  it('lukMark: ✓ / ✗ / · (unjudged)', () => {
    expect(lukMark(true)).toBe('✓');
    expect(lukMark(false)).toBe('✗');
    expect(lukMark(null)).toBe('·');
  });
  it('lukSpan takes {key,label} or a bare key', () => {
    expect(lukSpan('5d')).toEqual({ key: '5d', label: '5d' });
    expect(lukSpan({ key: 'all', label: 'All' })).toEqual({ key: 'all', label: 'All' });
  });
  it('lukLegendRows takes a dict or a list; NEGATIVE: blank texts dropped', () => {
    expect(lukLegendRows({ aplus: 'A+ — every rule met', none: '' })).toEqual([{ key: 'aplus', text: 'A+ — every rule met' }]);
    expect(lukLegendRows([{ key: 'listed', text: 'listed — a rule says not A+' }, { key: 'x', text: ' ' }]))
      .toEqual([{ key: 'listed', text: 'listed — a rule says not A+' }]);
    expect(lukLegendRows(null)).toEqual([]);
  });
});

describe('lukScreenCols', () => {
  const base: LukScreen = { key: 'premarket', title: 't', rows: [
    { rank: 1, symbol: 'AAA', price_text: '12.40', pm_chg_text: '+8.1%', cap_text: '$1.2B', avg_vol_text: '2.1M',
      px_vol_text: '$61M', vol_1w_text: '6.2%', tier_text: 'Lead', adr_text: 'ADR 6.1%' }] };
  it('object heads carry their own key', () => {
    expect(lukScreenCols({ ...base, heads: [{ key: 'symbol', label: 'Ticker' }, { key: 'cap_text', label: 'Cap' }] }))
      .toEqual([{ key: 'symbol', label: 'Ticker' }, { key: 'cap_text', label: 'Cap' }]);
  });
  it('string heads zip with the row fields present, in the spec order (the absent change fields skipped)', () => {
    const cols = lukScreenCols({ ...base, heads: ['#', 'Ticker', 'Price', 'Pre-mkt %', 'Cap'] });
    expect(cols.map((c) => c.key)).toEqual(['rank', 'symbol', 'price_text', 'pm_chg_text', 'cap_text']);
    expect(cols.map((c) => c.label)).toEqual(['#', 'Ticker', 'Price', 'Pre-mkt %', 'Cap']);
  });
  it('NEGATIVE: no heads → no columns', () => {
    expect(lukScreenCols({ ...base, heads: [] })).toEqual([]);
    expect(lukScreenCols({ ...base, heads: null })).toEqual([]);
  });
});

describe('lukChartTile — the served 5-minute tile under the house CmTile keys', () => {
  const t: LukTile = { symbol: 'AAA', href: '/sepa/AAA', setup: 'pullback_reversal', state: 'aplus', state_label: 'A+',
    bars5: [{ t: '2026-11-03T09:35', o: 1, h: 2, l: 0.5, c: 1.5, v: 10 }],
    curves5: [{ tone: 'ema9' as any, label: '9 EMA', values: [1.2] }], vol_avg5: null };
  it('maps bars5 / curves5 / vol_avg5', () => {
    const c = lukChartTile(t);
    expect(c.bars).toBe(t.bars5);
    expect(c.curves).toBe(t.curves5);
    expect(c.href).toBe('/sepa/AAA');
    expect(c.bands).toEqual([]); expect(c.stats).toEqual([]); expect(c.why).toBe('');
  });
  it('NEGATIVE: no served bars → an empty list (no chart), never a made-up bar', () => {
    const c = lukChartTile({ ...t, bars5: null });
    expect(c.bars).toEqual([]);
  });
});
