/* 🗺️ StockTitan sector heatmap links (Ajay 2026-09-24).
 *
 * StockTitan matches the sector EXACTLY (`sectors.find(s => s.name ===
 * sector)`) and a miss silently draws the whole S&P 500 map — a link that
 * looks like it worked. These pin every one of our eleven sector names to the
 * GICS name read off its own payload on 2026-09-24, and pin that a name we
 * cannot map gets NO link rather than a guessed one. */
import { describe, expect, it } from 'vitest';
import { STOCKTITAN_HEATMAP_URL, STOCKTITAN_SECTOR, stockTitanHeatmapUrl } from './rotation';

/* The eleven names from `window.__TREEMAP_API_DATA__.sectors[].name`. */
const THEIRS = [
  'Health Care', 'Information Technology', 'Consumer Discretionary', 'Financials',
  'Consumer Staples', 'Utilities', 'Materials', 'Industrials', 'Real Estate',
  'Energy', 'Communication Services',
];

describe('STOCKTITAN_SECTOR — ours (Yahoo) → theirs (GICS)', () => {
  it('maps all eleven, onto all eleven of theirs, one-to-one', () => {
    expect(Object.keys(STOCKTITAN_SECTOR)).toHaveLength(11);
    expect([...new Set(Object.values(STOCKTITAN_SECTOR))].sort()).toEqual([...THEIRS].sort());
  });

  it.each([
    ['Technology', 'Information Technology'],
    ['Healthcare', 'Health Care'],
    ['Financial Services', 'Financials'],
    ['Consumer Cyclical', 'Consumer Discretionary'],
    ['Consumer Defensive', 'Consumer Staples'],
    ['Basic Materials', 'Materials'],
  ])('the six that differ: %s → %s', (ours, theirs) => {
    expect(STOCKTITAN_SECTOR[ours]).toBe(theirs);
  });

  it('is frozen — nothing can quietly repoint a sector at runtime', () => {
    expect(Object.isFrozen(STOCKTITAN_SECTOR)).toBe(true);
  });
});

describe('stockTitanHeatmapUrl', () => {
  it('reproduces the exact link he pasted', () => {
    expect(stockTitanHeatmapUrl('Energy'))
      .toBe('https://www.stocktitan.net/stock-market-heatmap#sector=Energy');
  });

  it('encodes a two-word GICS name the way StockTitan writes its own hash', () => {
    expect(stockTitanHeatmapUrl('Technology'))
      .toBe(`${STOCKTITAN_HEATMAP_URL}#sector=Information%20Technology`);
  });

  it('round-trips through URLSearchParams — the parser StockTitan uses', () => {
    for (const ours of Object.keys(STOCKTITAN_SECTOR)) {
      const hash = stockTitanHeatmapUrl(ours)!.split('#')[1];
      expect(new URLSearchParams(hash).get('sector')).toBe(STOCKTITAN_SECTOR[ours]);
    }
  });

  it('an industry rides along, and a literal "&" cannot split it into two params', () => {
    const hash = stockTitanHeatmapUrl('Energy', 'Oil & Gas E&P')!.split('#')[1];
    const p = new URLSearchParams(hash);
    expect(p.get('sector')).toBe('Energy');
    expect(p.get('industry')).toBe('Oil & Gas E&P');
    expect([...p.keys()]).toEqual(['sector', 'industry']);
  });

  it('a blank industry adds no empty industry= param', () => {
    expect(stockTitanHeatmapUrl('Energy', '  ')).not.toContain('industry');
    expect(stockTitanHeatmapUrl('Energy', null)).not.toContain('industry');
  });

  it('trims a padded sector name rather than missing it', () => {
    expect(stockTitanHeatmapUrl('  Healthcare ')).toContain('sector=Health%20Care');
  });

  it.each([
    ['a theme id', 'ai_semis'],
    ['a haven', 'Gold miners'],
    ['GICS spelling of ours (it is theirs, not ours)', 'Information Technology'],
    ['wrong case', 'energy'],
    ['empty', ''],
    ['null', null],
    ['undefined', undefined],
  ])('NEGATIVE: %s gets NO link, never a guessed one', (_label, v) => {
    expect(stockTitanHeatmapUrl(v as string | null | undefined)).toBeNull();
  });
});
