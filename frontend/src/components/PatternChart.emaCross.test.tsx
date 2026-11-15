import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { barDomain, yFor, type CmTile } from '../lib/chartMaps';
import { volumePaneLayout } from '../lib/volumePane';

/* 🔀 The 9 / 21 EMA cross marks on a ➖ Fade card (2026-11-15). The server serves one marker per cross
 * {date, kind: 'ema_cross_up' | 'ema_cross_dn', label: the served sentence, price: the 9 EMA at the cross bar}; the
 * chart draws a small diamond on that price — green up, red down — with the served sentence as its <title>.
 * NEGATIVES: no marker → no diamond; a marker off the drawn bars → nothing; the BUY tag keeps its own glyph. */

const H = volumePaneLayout(190, 10, true).priceH;
const PAD_Y = 10;
const bars = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-11-13 10:${String(i).padStart(2, '0')}`, o: 10.9, h: 11.1, l: 10.7, c: 10.9 + (i % 2 ? 0.05 : -0.05), v: 1000,
}));
const UP = '🔀 9 EMA crossed above 21 EMA at 10:05 ET';
const DN = '🔀 9 EMA crossed under 21 EMA at 10:20 ET';
const tile = (markers: any[]): CmTile => ({
  symbol: 'OMH', href: '/sepa/OMH', bars, bands: [], lines: [], markers, stats: [], why: '',
});
const draw = (t: CmTile) => render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);

afterEach(() => cleanup());

describe('PatternChart — 🔀 EMA cross marks', () => {
  it('draws an up diamond and a down diamond with the served sentence as the title', () => {
    const t = tile([{ date: bars[5].t, kind: 'ema_cross_up', label: UP, price: 10.95 },
                    { date: bars[20].t, kind: 'ema_cross_dn', label: DN, price: 10.85 }]);
    const { container } = draw(t);
    const up = container.querySelector('[data-testid="pc-ema-cross-up"]') as SVGPolygonElement;
    const dn = container.querySelector('[data-testid="pc-ema-cross-dn"]') as SVGPolygonElement;
    expect(up).not.toBeNull();
    expect(dn).not.toBeNull();
    expect(up.getAttribute('class')).toBe('pc-ema-cross pc-ema-cross-up');
    expect(dn.getAttribute('class')).toBe('pc-ema-cross pc-ema-cross-dn');
    expect(up.getAttribute('fill')).toContain('--positive');
    expect(dn.getAttribute('fill')).toContain('--negative');
    expect(up.querySelector('title')?.textContent).toBe(UP);
    expect(dn.querySelector('title')?.textContent).toBe(DN);
    const d = barDomain(t.bars, t.bands, t.lines, 6, t.curves);
    const yTop = Number(up.getAttribute('points')!.split(' ')[0].split(',')[1]);
    expect(yTop).toBeCloseTo(yFor(10.95, d, H, PAD_Y) - 3.6, 3);           // on the served EMA price
  });

  it('a marker without a price sits on the bar close', () => {
    const t = tile([{ date: bars[7].t, kind: 'ema_cross_up', label: UP }]);
    const { container } = draw(t);
    const up = container.querySelector('[data-testid="pc-ema-cross-up"]') as SVGPolygonElement;
    const d = barDomain(t.bars, t.bands, t.lines, 6, t.curves);
    const yTop = Number(up.getAttribute('points')!.split(' ')[0].split(',')[1]);
    expect(yTop).toBeCloseTo(yFor(bars[7].c, d, H, PAD_Y) - 3.6, 3);
  });

  it('NEGATIVE: no cross marker → no diamond; a marker off the drawn bars → nothing', () => {
    expect(draw(tile([])).container.querySelector('.pc-ema-cross')).toBeNull();
    cleanup();
    const { container } = draw(tile([{ date: '2026-11-12 10:05', kind: 'ema_cross_up', label: UP, price: 11 }]));
    expect(container.querySelector('.pc-ema-cross')).toBeNull();
  });

  it('NEGATIVE: the A+ BUY tag beside a cross keeps its own tag, never a diamond', () => {
    const { container } = draw(tile([{ date: bars[10].t, kind: 'buy', label: 'A+' },
                                      { date: bars[5].t, kind: 'ema_cross_up', label: UP, price: 10.95 }]));
    expect(container.querySelectorAll('.pc-ema-cross').length).toBe(1);
    expect(Array.from(container.querySelectorAll('svg text')).some((n) => n.textContent === 'A+')).toBe(true);
  });
});
