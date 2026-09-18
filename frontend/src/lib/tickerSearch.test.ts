import { describe, it, expect } from 'vitest';
import {
  TICKER_RESULT_LIMIT,
  coerceTickerHits,
  isTickerRelevant,
  mergeRows,
  pinnedSymbol,
  rankTickers,
  rowKey,
  sectionHeaderAt,
  tickerRoute,
} from './tickerSearch';
import type { NavEntry } from './navSearch';

/* tickerSearch — the ranking/merging half of "tickers in the same ⌘K field"
 * (Ajay 2026-09-18). Every payload below is the LIVE body captured from
 *   rtk proxy curl -s -H "X-User-Email: …" \
 *     "http://127.0.0.1:8000/symbol-search?q=<q>"
 * on 2026-09-18, not hand-written JSON. */

const P = {
  digital: { q: 'digital', cached: true, results: [
    { symbol: 'WDC',  display_symbol: 'WDC',  name: 'Western Digital Corp',              type: 'Common Stock' },
    { symbol: 'DLR',  display_symbol: 'DLR',  name: 'Digital Realty Trust Inc',          type: 'Common Stock' },
    { symbol: 'GEN',  display_symbol: 'GEN',  name: 'Gen Digital Inc',                   type: 'Common Stock' },
    { symbol: 'DOCN', display_symbol: 'DOCN', name: 'DigitalOcean Holdings Inc',         type: 'Common Stock' },
    { symbol: 'GLXY', display_symbol: 'GLXY', name: 'Galaxy Digital Inc',                type: 'Common Stock' },
    { symbol: 'IDCC', display_symbol: 'IDCC', name: 'InterDigital Inc',                  type: 'Common Stock' },
    { symbol: 'APLD', display_symbol: 'APLD', name: 'Applied Digital Corp',              type: 'Common Stock' },
    { symbol: 'CIFR', display_symbol: 'CIFR', name: 'Cipher Digital Inc',                type: 'Common Stock' },
    { symbol: 'IOND', display_symbol: 'IOND', name: 'Ionic Digital Inc',                 type: 'Common Stock' },
    { symbol: 'AD',   display_symbol: 'AD',   name: 'Array Digital Infrastructure Inc',  type: 'Common Stock' },
    { symbol: 'DBRG', display_symbol: 'DBRG', name: 'DigitalBridge Group Inc',           type: 'Common Stock' },
  ] },
  docn: { q: 'DOCN', cached: true, results: [
    { symbol: 'DOCN', display_symbol: 'DOCN', name: 'DIGITALOCEAN HOLDINGS INC', type: 'Common Stock' },
  ] },
  amd: { q: 'amd', cached: true, results: [
    { symbol: 'AMD', display_symbol: 'AMD', name: 'ADVANCED MICRO DEVICES', type: 'Common Stock' },
    { symbol: 'CPT', display_symbol: 'CPT', name: 'Camden Property Trust',  type: 'Common Stock' },
    { symbol: 'DOX', display_symbol: 'DOX', name: 'Amdocs Ltd',             type: 'Common Stock' },
    { symbol: 'CAC', display_symbol: 'CAC', name: 'Camden National Corp',   type: 'Common Stock' },
  ] },
  iv: { q: 'iv', cached: true, results: [
    { symbol: 'IBKR', display_symbol: 'IBKR', name: 'Interactive Brokers Group Inc',  type: 'Common Stock' },
    { symbol: 'ISRG', display_symbol: 'ISRG', name: 'Intuitive Surgical Inc',         type: 'Common Stock' },
    { symbol: 'PGR',  display_symbol: 'PGR',  name: 'Progressive Corp',               type: 'Common Stock' },
    { symbol: 'VRT',  display_symbol: 'VRT',  name: 'Vertiv Holdings Co',             type: 'Common Stock' },
    { symbol: 'CL',   display_symbol: 'CL',   name: 'Colgate-Palmolive Co',           type: 'Common Stock' },
    { symbol: 'TTWO', display_symbol: 'TTWO', name: 'Take-Two Interactive Software Inc', type: 'Common Stock' },
    { symbol: 'ROIV', display_symbol: 'ROIV', name: 'Roivant Sciences Ltd',           type: 'Common Stock' },
  ] },
  gnt:  { q: 'gnt',  cached: true, results: [{ symbol: 'GNT',  display_symbol: 'GNT',  name: 'GAMCO NATURAL RESOURCES GOLD', type: 'Closed-End Fund' }] },
  maps: { q: 'maps', cached: true, results: [{ symbol: 'MAPS', display_symbol: 'MAPS', name: 'WM TECHNOLOGY INC',            type: 'Common Stock' }] },
  lab:  { q: 'lab',  cached: true, results: [
    { symbol: 'LAB',  display_symbol: 'LAB',  name: 'STANDARD BIOTOOLS INC',  type: 'Common Stock' },
    { symbol: 'ABT',  display_symbol: 'ABT',  name: 'Abbott Laboratories',    type: 'Common Stock' },
    { symbol: 'ALAB', display_symbol: 'ALAB', name: 'Astera Labs, Inc',       type: 'Common Stock' },
  ] },
  path: { q: 'path', cached: true, results: [
    { symbol: 'PATH', display_symbol: 'PATH', name: 'UIPATH INC - CLASS A',   type: 'Common Stock' },
    { symbol: 'PATH', display_symbol: 'PATH', name: 'UiPath Inc',             type: 'Common Stock' },
    { symbol: 'CMPS', display_symbol: 'CMPS', name: 'Compass Pathways PLC',   type: 'Common Stock' },
  ] },
  copa: { q: 'copa', cached: true, results: [
    { symbol: 'COPA', display_symbol: 'COPA', name: 'THEMES COPPER MINERS ETF', type: 'ETP' },
    { symbol: 'CPRT', display_symbol: 'CPRT', name: 'Copart Inc',               type: 'Common Stock' },
  ] },
  ravi: { q: 'ravi', cached: true, results: [
    { symbol: 'RAVI', display_symbol: 'RAVI', name: 'NT ULTRASHRT FI ETF', type: 'ETP' },
    { symbol: 'EVC',  display_symbol: 'EVC',  name: 'Entravision Communications Corp', type: 'Common Stock' },
  ] },
  zzzzz: { q: 'zzzzz', cached: true, results: [] },
};

/** The real menu labels that collide with a real symbol (measured 2026-09-18). */
const page = (label: string, to: string): NavEntry =>
  ({ label, to, feature: undefined, group: 'Primary', keywords: [] });

const REAL_PAGES: NavEntry[] = [
  page('🗺️ Chart Maps', '/chart-maps'),
  page('⚡ Signal Lab', '/signal-lab'),
  page('📚 Learning Path', '/learning-path'),
  page('Kell (CoPA)', '/kell'),
  page("Ravi's Strategy", '/ravi'),
  page('SEPA ▸ Supply / Demand', '/sepa?tab=supply'),
];

const syms = (rows: ReturnType<typeof rankTickers>) => rows.map((r) => r.symbol);

describe('tickerSearch — rankTickers on the live payloads', () => {
  it('"digital" puts DOCN in the top two — name-prefix beats provider order', () => {
    const rows = rankTickers('digital', P.digital);
    // Every name that STARTS with "digital" first, in provider order
    // (DLR, DOCN, DBRG), then the names that merely contain it (WDC).
    expect(syms(rows)).toEqual(['DLR', 'DOCN', 'DBRG', 'WDC']);
    expect(syms(rows).indexOf('DOCN')).toBeLessThanOrEqual(1);
    expect(rows).toHaveLength(TICKER_RESULT_LIMIT);
  });

  it('"docn" and "DOCN" both give one row routed at /sepa/DOCN', () => {
    for (const q of ['docn', 'DOCN', '  docn  ']) {
      const rows = rankTickers(q, P.docn);
      expect(rows).toHaveLength(1);
      expect(rows[0].to).toBe('/sepa/DOCN');
      expect(rows[0].name).toBe('DIGITALOCEAN HOLDINGS INC');
      expect(rows[0].kind).toBe('ticker');
    }
  });

  it('"amd" keeps AMD first and Amdocs, and DROPS Camden Property / Camden National', () => {
    const rows = syms(rankTickers('amd', P.amd));
    expect(rows[0]).toBe('AMD');
    expect(rows).toContain('DOX');
    expect(rows).not.toContain('CPT');
    expect(rows).not.toContain('CAC');
  });

  it('"iv" returns NOTHING — every Finnhub row for it is unrelated (negative)', () => {
    expect(rankTickers('iv', P.iv)).toEqual([]);
  });

  it('"gnt" keeps a Closed-End Fund — type is shown, never filtered', () => {
    const rows = rankTickers('gnt', P.gnt);
    expect(rows[0].symbol).toBe('GNT');
    expect(rows[0].type).toBe('Closed-End Fund');
  });

  it('a duplicate symbol is deduped, first row wins (PATH came back twice)', () => {
    const rows = rankTickers('path', P.path);
    expect(syms(rows).filter((s) => s === 'PATH')).toHaveLength(1);
    expect(rows[0].name).toBe('UIPATH INC - CLASS A');
  });

  it('an empty provider body gives no rows (negative)', () => {
    expect(rankTickers('zzzzz', P.zzzzz)).toEqual([]);
  });

  it('a blank query never ranks anything (negative)', () => {
    expect(rankTickers('', P.docn)).toEqual([]);
    expect(rankTickers('   ', P.docn)).toEqual([]);
  });

  it('honours an explicit limit', () => {
    expect(rankTickers('digital', P.digital, 2)).toHaveLength(2);
    expect(rankTickers('digital', P.digital, 0)).toEqual([]);
  });
});

describe('tickerSearch — coerceTickerHits fails open on junk (negatives)', () => {
  it.each([
    ['null', null],
    ['undefined', undefined],
    ['an empty object', {}],
    ['a non-array results', { results: 'nope' }],
    ['a number', 7],
    ['a string', 'DOCN'],
    ['a boolean', true],
    ['rows that are not objects', { results: [null, 3, 'x', []] }],
    ['a row with no symbol', { results: [{ name: 'x' }] }],
    ['a row with a blank symbol', [{ symbol: '   ' }]],
    ['a row with a non-string symbol', { results: [{ symbol: 42 }] }],
  ])('%s → [] and never throws', (_label, raw) => {
    expect(() => coerceTickerHits(raw)).not.toThrow();
    expect(coerceTickerHits(raw)).toEqual([]);
    expect(() => rankTickers('docn', raw)).not.toThrow();
    expect(rankTickers('docn', raw)).toEqual([]);
  });

  it('accepts a bare array as well as the envelope', () => {
    expect(coerceTickerHits(P.docn.results)).toHaveLength(1);
    expect(coerceTickerHits(P.docn)).toHaveLength(1);
  });

  it('fills missing name/type and prefers display_symbol, upper-cased', () => {
    const hits = coerceTickerHits({ results: [{ symbol: 'docn', display_symbol: 'docn.x' }] });
    expect(hits[0]).toEqual({ symbol: 'DOCN.X', name: '', type: 'Common Stock' });
  });

  it('caps a huge body at 25 rows', () => {
    const results = Array.from({ length: 200 }, (_, i) => ({ symbol: `S${i}` }));
    expect(coerceTickerHits({ results })).toHaveLength(25);
  });
});

describe('tickerSearch — isTickerRelevant', () => {
  it('matches on the symbol prefix and on a name word prefix', () => {
    expect(isTickerRelevant('doc', { symbol: 'DOCN', name: '', type: '' })).toBe(true);
    expect(isTickerRelevant('digital', { symbol: 'WDC', name: 'Western Digital Corp', type: '' })).toBe(true);
  });
  it('does not match mid-word or a blank query (negative)', () => {
    expect(isTickerRelevant('iv', { symbol: 'IBKR', name: 'Interactive Brokers Group Inc', type: '' })).toBe(false);
    expect(isTickerRelevant('', { symbol: 'DOCN', name: '', type: '' })).toBe(false);
  });
});

describe('tickerSearch — the pin guard (the five measured collisions)', () => {
  it.each([
    ['maps', P.maps, 'MAPS'],
    ['lab',  P.lab,  'LAB'],
    ['path', P.path, 'PATH'],
    ['copa', P.copa, 'COPA'],
    ['ravi', P.ravi, 'RAVI'],
  ])('"%s" is NOT pinned — a page in his menu is named that word (negative)', (q, payload, sym) => {
    const tickers = rankTickers(q, payload);
    expect(tickers[0].symbol).toBe(sym);              // the symbol is real and ranked first
    expect(pinnedSymbol(q, tickers, REAL_PAGES)).toBeNull();
  });

  it.each([
    ['amd',  P.amd,  'AMD'],
    ['docn', P.docn, 'DOCN'],
    ['gnt',  P.gnt,  'GNT'],
  ])('"%s" IS pinned against the same page list', (q, payload, sym) => {
    expect(pinnedSymbol(q, rankTickers(q, payload), REAL_PAGES)).toBe(sym);
  });

  it('nothing is pinned when the query is not the symbol exactly (negative)', () => {
    expect(pinnedSymbol('digital', rankTickers('digital', P.digital), REAL_PAGES)).toBeNull();
    expect(pinnedSymbol('doc', rankTickers('doc', P.docn), REAL_PAGES)).toBeNull();
  });

  it('nothing is pinned with no tickers or a blank query (negative)', () => {
    expect(pinnedSymbol('docn', [], REAL_PAGES)).toBeNull();
    expect(pinnedSymbol('', rankTickers('docn', P.docn), REAL_PAGES)).toBeNull();
  });
});

describe('tickerSearch — mergeRows', () => {
  it('puts the pin at index 0 and keeps every page row in searchNav order below it', () => {
    const tickers = rankTickers('amd', P.amd);
    const rows = mergeRows(REAL_PAGES, tickers, 'amd');
    expect(rows[0]).toMatchObject({ kind: 'ticker', symbol: 'AMD' });
    expect(rows.slice(1, 1 + REAL_PAGES.length).map((r) => (r.kind === 'page' ? r.entry.to : null)))
      .toEqual(REAL_PAGES.map((p) => p.to));
  });

  it('no page row moves when the tickers go from [] to a full section', () => {
    const before = mergeRows(REAL_PAGES, [], 'digital').filter((r) => r.kind === 'page');
    const after = mergeRows(REAL_PAGES, rankTickers('digital', P.digital), 'digital');
    expect(after.slice(0, REAL_PAGES.length)).toEqual(before);
    expect(after.slice(REAL_PAGES.length).every((r) => r.kind === 'ticker')).toBe(true);
  });

  it('a blocked pin stays in the ticker section below the pages', () => {
    const rows = mergeRows(REAL_PAGES, rankTickers('maps', P.maps), 'maps');
    expect(rows[0].kind).toBe('page');
    expect(rows[rows.length - 1]).toMatchObject({ kind: 'ticker', symbol: 'MAPS' });
  });

  it('a pure-ticker query is just the ticker rows', () => {
    const rows = mergeRows([], rankTickers('docn', P.docn), 'docn');
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ kind: 'ticker', symbol: 'DOCN', to: '/sepa/DOCN' });
  });

  it('a pure-nav query is byte-identical to the pages it was given', () => {
    const rows = mergeRows(REAL_PAGES, [], 'chart');
    expect(rows.map((r) => (r.kind === 'page' ? r.entry : null))).toEqual(REAL_PAGES);
  });
});

describe('tickerSearch — rowKey and sectionHeaderAt', () => {
  it('a page key and a ticker key can never collide', () => {
    const rows = mergeRows(REAL_PAGES, rankTickers('digital', P.digital), 'digital');
    const keys = rows.map(rowKey);
    expect(new Set(keys).size).toBe(keys.length);
    expect(keys).toContain('page:/chart-maps');
    expect(keys).toContain('ticker:DOCN');
  });

  it('labels the two sections when both kinds are on screen', () => {
    const rows = mergeRows(REAL_PAGES, rankTickers('digital', P.digital), 'digital');
    expect(sectionHeaderAt(rows, 0)).toBe('Pages');
    expect(sectionHeaderAt(rows, REAL_PAGES.length)).toBe('Tickers');
    expect(sectionHeaderAt(rows, 1)).toBeNull();
  });

  it('labels nothing when only one kind is present (negative)', () => {
    const only = mergeRows([], rankTickers('docn', P.docn), 'docn');
    expect(only.map((_, i) => sectionHeaderAt(only, i))).toEqual([null]);
    const pages = mergeRows(REAL_PAGES, [], 'chart');
    expect(pages.map((_, i) => sectionHeaderAt(pages, i)).filter(Boolean)).toEqual([]);
    expect(sectionHeaderAt([], 0)).toBeNull();
  });

  it('a lone pinned ticker above the pages gets no header (negative)', () => {
    const rows = mergeRows(REAL_PAGES, rankTickers('docn', P.docn), 'docn');
    expect(rows[0]).toMatchObject({ kind: 'ticker', symbol: 'DOCN' });
    expect(rows.map((_, i) => sectionHeaderAt(rows, i)).filter(Boolean)).toEqual([]);
  });
});

describe('tickerSearch — tickerRoute', () => {
  it('trims and upper-cases', () => {
    expect(tickerRoute(' docn ')).toBe('/sepa/DOCN');
    expect(tickerRoute('AMD')).toBe('/sepa/AMD');
  });
});
