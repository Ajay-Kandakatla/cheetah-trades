import { describe, it, expect } from 'vitest';
import { parseSiMap, siChip, SI_NOT_WARMED_TEXT, SI_REQUEST_FAILED_TEXT, type ShortInterestRead } from './shortInterest';

/* 🩳 Short interest — the FE shapes the served block and prints it verbatim.
 * Ajay 2026-10-03: "can you add this field to all our chart maps scan. also
 * the individual tickers please". The negatives carry the weight: a missing
 * read must render NOTHING, never a zero. */

const EOSE = {
  symbol: 'EOSE', status: 'ok',
  settlement_date: '2026-09-15', published_on: '2026-09-24', prev_settlement_date: '2026-08-31',
  si_shares: 120015346, prev_si_shares: 111323398, si_change_pct: 7.8,
  avg_daily_volume: 29047980, days_to_cover: 4.13,
  float_shares: 357328674, float_asof: '2026-09-04', float_source: 'yfinance floatShares (shares_cache)', pct_of_float: 33.59,
  shares_outstanding: 361687337, shares_asof: '2026-09-04', shares_source: 'yfinance sharesOutstanding (shares_cache)', pct_of_shares_out: 33.18,
  headline_basis: 'float', stale: false, stale_reason: null,
  next_settlement_date: '2026-09-30', next_due_on: '2026-10-13',
  source: 'FINRA short interest (Rule 4560) via Massive /stocks/v1/short-interest',
  fetched_at: '2026-10-03T22:40:00Z',
  chip: '🩳 SI 33.6% float · 4.1d · 9/15',
  title: '🩳 Short interest — FINRA settlement 2026-09-15 (published ~2026-09-24). A count of open short positions — not a forecast.',
  rows: [{ k: 'Settlement', v: '2026-09-15 (FINRA; published ~2026-09-24)' }],
} as unknown as ShortInterestRead;

describe('siChip', () => {
  it('returns the served text and title verbatim', () => {
    expect(siChip(EOSE)).toEqual({ text: EOSE.chip, title: EOSE.title, stale: false });
  });

  it('a stale block says so through the flag (the text is served as-is)', () => {
    const s = { ...EOSE, status: 'stale', chip: '🩳 SI 30.6% shs out · 5.0d · 8/31 · stale' } as ShortInterestRead;
    expect(siChip(s)).toEqual({ text: s.chip, title: s.title, stale: true });
  });

  it('NEGATIVE: null, undefined, no_record, empty chip and a non-string chip are all null', () => {
    expect(siChip(null)).toBeNull();
    expect(siChip(undefined)).toBeNull();
    expect(siChip({ ...EOSE, status: 'no_record', chip: null } as ShortInterestRead)).toBeNull();
    expect(siChip({ ...EOSE, status: 'no_record' } as ShortInterestRead)).toBeNull();
    expect(siChip({ ...EOSE, chip: '' } as ShortInterestRead)).toBeNull();
    expect(siChip({ ...EOSE, chip: '   ' } as ShortInterestRead)).toBeNull();
    expect(siChip({ ...EOSE, chip: 42 } as unknown as ShortInterestRead)).toBeNull();
  });
});

describe('parseSiMap', () => {
  it('keeps a well-formed block and uppercases its key', () => {
    const m = parseSiMap({ items: { eose: EOSE }, n: 1, max_symbols: 200 });
    expect(Object.keys(m)).toEqual(['EOSE']);
    expect(m.EOSE.chip).toBe(EOSE.chip);
    expect(m.EOSE.rows).toEqual(EOSE.rows);
  });

  it('keeps a no_record block (chip null is a valid served value)', () => {
    const nr = { symbol: 'FOO', status: 'no_record', chip: null, title: 'Short interest: no FINRA record on file for FOO at the last warm — not read.',
                 rows: [{ k: 'Short interest', v: 'not read — no FINRA record at the last warm' }] };
    const m = parseSiMap({ items: { FOO: nr } });
    expect(m.FOO.chip).toBeNull();
    expect(siChip(m.FOO)).toBeNull();
  });

  it('NEGATIVE: null, an array, items as an array, a non-string title → {}', () => {
    expect(parseSiMap(null)).toEqual({});
    expect(parseSiMap(undefined)).toEqual({});
    expect(parseSiMap('x')).toEqual({});
    expect(parseSiMap([])).toEqual({});
    expect(parseSiMap({})).toEqual({});
    expect(parseSiMap({ items: [] })).toEqual({});
    expect(parseSiMap({ items: null })).toEqual({});
    expect(parseSiMap({ items: { X: { title: 3 } } })).toEqual({});
  });

  it('NEGATIVE: drops an entry whose chip is neither a string nor null; keeps its neighbours', () => {
    const m = parseSiMap({ items: { BAD: { ...EOSE, chip: 0 }, MISS: { ...EOSE, chip: undefined }, EOSE } });
    expect(Object.keys(m)).toEqual(['EOSE']);
  });

  it('NEGATIVE: malformed rows are dropped, never printed as [object Object]', () => {
    const m = parseSiMap({ items: { EOSE: { ...EOSE, rows: [{ k: 'a', v: 'b' }, { k: 1, v: 'x' }, null, 'str'] } } });
    expect(m.EOSE.rows).toEqual([{ k: 'a', v: 'b' }]);
    const n = parseSiMap({ items: { EOSE: { ...EOSE, rows: 'nope' } } });
    expect(n.EOSE.rows).toEqual([]);
  });

  it('the not-warmed line never prints a number', () => {
    expect(SI_NOT_WARMED_TEXT).not.toMatch(/\d/);
    expect(SI_NOT_WARMED_TEXT).toMatch(/^Not read/);
  });

  it('NEGATIVE: the request-failed line never prints a number and never claims "no record"', () => {
    expect(SI_REQUEST_FAILED_TEXT).not.toMatch(/\d/);
    expect(SI_REQUEST_FAILED_TEXT).toMatch(/^Not read/);
    expect(SI_REQUEST_FAILED_TEXT).not.toMatch(/no short-interest record/);
    expect(SI_REQUEST_FAILED_TEXT).not.toBe(SI_NOT_WARMED_TEXT);
  });
});
