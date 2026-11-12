import { describe, expect, it } from 'vitest';
import {
  LUK_BASE, LUK_CAT_PARAM, LUK_REFRESH_FALLBACK_MS, LUK_SCAN_PATH, LUK_SORT_PARAM, LUK_SPAN_PARAM, LUK_SUB_PARAM, LUK_TAB,
  LUK_TAPE_PATH, lukChartTile, lukHref, lukInWindow, lukLegendRows, lukLivePct, lukLiveLevels, lukMark, lukNextReadMs,
  lukQuery, lukRefreshMs, lukScanLanded, lukScreenCols, lukSpan, lukText, parseLukSub, type LukBoard, type LukScreen,
  type LukTile,
} from './luk';
import { GG_CAT_PARAM, GG_SCAN_PATH, GG_SORT_PARAM, ggScanAdvanced, type GgBoard } from './gajjala';

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

/* 🏁 2026-11-02 (Ajay: "Can you make Luk's track record similar to Gajjal's") — the 🏁 ✅ / ❌ category chip and the ✅
 * wins-first chip ride the URL as 🚩's do (backend ledger.CATEGORY_PARAM / SORT_PARAM), FE-only. */
describe('luk — the 🏁 chip params (2026-11-02)', () => {
  it('cat / sort == 🚩\'s param names (== backend ledger.CATEGORY_PARAM / SORT_PARAM)', () => {
    expect(LUK_CAT_PARAM).toBe('cat');
    expect(LUK_SORT_PARAM).toBe('sort');
    expect(LUK_CAT_PARAM).toBe(GG_CAT_PARAM);
    expect(LUK_SORT_PARAM).toBe(GG_SORT_PARAM);
  });
  it('NEGATIVE: never on the GET — lukQuery drops cat / sort', () => {
    const q = lukQuery({ sub: 'track_record', span: '5d', ...({ cat: 'win', sort: 'rang' } as any) });
    expect(q).toBe('sub=track_record&span=5d');
    const p = new URLSearchParams(q);
    expect(p.has(LUK_CAT_PARAM)).toBe(false);
    expect(p.has(LUK_SORT_PARAM)).toBe(false);
  });
  it('NEGATIVE: a sub click (lukHref) carries no cat / sort', () => {
    const p = new URLSearchParams(lukHref('track_record').split('?')[1]);
    expect(p.has(LUK_CAT_PARAM)).toBe(false);
    expect(p.has(LUK_SORT_PARAM)).toBe(false);
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

/* 🔄 2026-11-11, Ajay: "Can you put an ondeman scan button for Luk' scans too" (lukscan WP-LUK-FE). */
describe('🔄 Luk scan now — the route and the landed rule', () => {
  it('LUK_SCAN_PATH is the api route string', () => {
    expect(LUK_SCAN_PATH).toBe('/chart-maps/luk/scan');
    expect(LUK_SCAN_PATH.startsWith(LUK_BASE)).toBe(true);
  });
  it('NEGATIVE: never 🚩 Gajjala\'s scan route', () => {
    expect(LUK_SCAN_PATH).not.toBe(GG_SCAN_PATH);
    expect(LUK_SCAN_PATH).not.toMatch(/gajjala/);
  });
  const A = '2026-11-11T15:31:00+00:00';
  const B = '2026-11-11T15:33:12+00:00';
  const board = (at: unknown, state: unknown): LukBoard => ({ tab: 'luk', title: 'T',
    pass: at === undefined ? undefined : { at: at as string | null },
    scan: state === undefined ? undefined : { state: state as string } });
  const rows: Array<[string, unknown, unknown, string | null | undefined, boolean]> = [
    ['moved, idle → landed', B, 'idle', A, true],
    ['moved, closed → landed', B, 'closed', A, true],
    ['moved, no scan block → landed', B, undefined, A, true],
    ['moved, no latest_at → landed', B, 'idle', null, true],
    ['NEGATIVE: same stamp → not landed', A, 'idle', A, false],
    ['NEGATIVE: moved but a pass still running → not landed', B, 'scanning', A, false],
    ['NEGATIVE: no pass.at → not landed', null, 'idle', A, false],
    ['NEGATIVE: blank pass.at → not landed', '', 'idle', A, false],
    ['NEGATIVE: no pass block → not landed', undefined, 'idle', A, false],
  ];
  for (const [name, at, state, latest, want] of rows) {
    it(`lukScanLanded == ggScanAdvanced: ${name}`, () => {
      const b = board(at, state);
      expect(lukScanLanded(b, latest)).toBe(want);
      expect(lukScanLanded(b, latest)).toBe(ggScanAdvanced(b as unknown as GgBoard, latest));
    });
  }
  it('NEGATIVE: no board → not landed', () => {
    expect(lukScanLanded(null, A)).toBe(false);
    expect(lukScanLanded(undefined, A)).toBe(false);
  });
});

/* 🔴 2026-11-12 realtime cards (lukrt spec §3.5). Ajay, verbatim: "Luks scan is not realtime I see all dated values can
 * you make it realtime". The four helpers read SERVED fields only; NEGATIVES for every malformed shape. */
describe('🔴 lukInWindow', () => {
  it('a positive served refresh_sec → in window', () => {
    expect(lukInWindow({ session: { refresh_sec: 300 } })).toBe(true);
  });
  for (const bad of [0, -1, null, undefined, '300', Number.NaN, Number.POSITIVE_INFINITY]) {
    it(`NEGATIVE: refresh_sec ${String(bad)} → closed`, () => {
      expect(lukInWindow({ session: { refresh_sec: bad } })).toBe(false);
    });
  }
  it('NEGATIVE: no board / no session → closed', () => {
    expect(lukInWindow(null)).toBe(false);
    expect(lukInWindow({})).toBe(false);
  });
});

describe('🔴 lukLiveLevels', () => {
  const lv = { trigger: 4.1, stop: 3.9, tf: '5m' };
  it('each served live_level verbatim, keyed by the upper-cased trimmed symbol', () => {
    const out = lukLiveLevels([{ symbol: ' hq ', live_level: lv } as unknown as LukTile]);
    expect(out).toEqual({ HQ: lv });
    expect(out.HQ).toBe(lv);
  });
  it('NEGATIVE: null / absent / non-object live_level (a stopped card) → absent; a blank symbol → absent', () => {
    const tiles = [
      { symbol: 'AAA', live_level: null }, { symbol: 'BBB' }, { symbol: 'CCC', live_level: 'x' },
      { symbol: 'DDD', live_level: [1, 2] }, { symbol: '  ', live_level: lv },
    ] as unknown as LukTile[];
    expect(lukLiveLevels(tiles)).toEqual({});
    expect(lukLiveLevels(null)).toEqual({});
  });
});

describe('🔴 lukNextReadMs', () => {
  it('a positive served pass.next_read_sec → × 1000', () => {
    expect(lukNextReadMs({ pass: { next_read_sec: 30 } })).toBe(30_000);
    expect(lukNextReadMs({ pass: { next_read_sec: 47.5 } })).toBe(47_500);
  });
  for (const bad of [0, -30, null, undefined, '30', Number.NaN, Number.POSITIVE_INFINITY]) {
    it(`NEGATIVE: next_read_sec ${String(bad)} → null (the cadence interval)`, () => {
      expect(lukNextReadMs({ pass: { next_read_sec: bad } })).toBeNull();
    });
  }
  it('NEGATIVE: no board / no pass → null', () => {
    expect(lukNextReadMs(null)).toBeNull();
    expect(lukNextReadMs({})).toBeNull();
  });
});

describe('🔴 lukLivePct', () => {
  it('the served pct_text inside a served vs with a kind', () => {
    expect(lukLivePct({ live_vs: { kind: 'between', text: 'w', pct_text: 'served pct' } })).toBe('served pct');
  });
  for (const [name, t] of [
    ['no live_vs', {}], ['a vs without pct_text', { live_vs: { kind: 'between', text: 'w' } }],
    ['a blank pct_text', { live_vs: { kind: 'between', text: 'w', pct_text: '  ' } }],
    ['a number pct_text', { live_vs: { kind: 'between', text: 'w', pct_text: 1.2 } }],
    ['a pct_text with no kind', { live_vs: { text: 'w', pct_text: 'served pct' } }],
    ['a pct_text with a blank kind', { live_vs: { kind: '', text: 'w', pct_text: 'served pct' } }],
    ['not a tile', null],
  ] as const) {
    it(`NEGATIVE: ${name} → null`, () => {
      expect(lukLivePct(t)).toBeNull();
    });
  }
});
