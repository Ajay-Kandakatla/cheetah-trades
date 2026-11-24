/* 🕯 2026-11-23 — NEGATIVE byte-identity for the 1-min candle look (Ajay: "On the 1 mins chart make the bard lil more
 * bright please." · "Make them more separted"). The snapshot file next to this test was RECORDED with the PatternChart.tsx
 * of HEAD before candleLook existed (the file swapped in, `vitest -u` on this file only, the new file put back); it is
 * never re-recorded by this change. A daily chart, a 5-min and a 15-min Watch-style chart (bold EMAs + served axis +
 * extended-hours bars) and the 📺 video look must render that markup byte for byte without candleLook. */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import type { CmAxis, CmTile } from '../lib/chartMaps';

afterEach(() => cleanup());

const N = 30;
const stamp = (m: number) => `2026-11-20 ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const intraday = (step: number) => Array.from({ length: N }, (_, i) => ({
  t: stamp(8 * 60 + 30 + i * step), o: 4 + (i % 4) * 0.03, h: 4.2 + (i % 5) * 0.02, l: 3.9, c: 4 + ((i + 1) % 4) * 0.03,
  v: 2000 + i * 10, ...(i < 6 ? { s: 'pre' } : {}),
}));
const daily = Array.from({ length: N }, (_, i) => ({
  t: `2026-10-${String(i + 1).padStart(2, '0')}`, o: 20 + i * 0.1, h: 20.5 + i * 0.1, l: 19.6 + i * 0.1,
  c: 20 + i * 0.1 + (i % 2 ? 0.2 : -0.15), v: 50000 + i,
}));
const tile = (bars: any[], over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'OMH', href: '/sepa/OMH', bars, bands: [], lines: [], stats: [], why: '',
  curves: [
    { tone: 'ema9', label: '9 EMA', values: bars.map((_, i) => 4 + i * 0.002) },
    { tone: 'ema21', label: '21 EMA', values: bars.map((_, i) => 4.01 + i * 0.001) },
  ],
  ...over,
} as CmTile);
const axis = (slots: number, first: number): CmAxis => ({
  slots, x: Array.from({ length: N }, (_, i) => first + i),
  shade: [{ from_slot: 0, to_slot: first + 6, kind: 'pre' }],
  ticks: [{ slot: 0, label: '04:00' }, { slot: slots, label: '20:00' }],
});
const html = (el: JSX.Element) => {
  const { container } = render(<MemoryRouter>{el}</MemoryRouter>);
  const out = container.innerHTML;
  cleanup();
  return out;
};

describe('🕯 NEGATIVE: every non-1m chart is HEAD\'s markup byte for byte', () => {
  it('daily card (no axis, no bold)', () => {
    expect(html(<PatternChart tile={tile(daily)} />)).toMatchSnapshot();
  });
  it('5-min Watch frame (chartOnly, bold, served axis, ext bars)', () => {
    expect(html(<PatternChart tile={tile(intraday(5))} chartOnly emaStyle="bold" axis={axis(192, 54)} height={180} />))
      .toMatchSnapshot();
  });
  it('15-min Watch frame (chartOnly, bold, served axis, ext bars, fitted viewW)', () => {
    expect(html(<PatternChart tile={tile(intraday(15))} chartOnly emaStyle="bold" axis={axis(64, 18)} viewW={900} height={180} />))
      .toMatchSnapshot();
  });
  it('📺 video look card', () => {
    expect(html(<PatternChart tile={tile(intraday(5))} look="video" axis={axis(192, 54)} />)).toMatchSnapshot();
  });
  it('candleLook={undefined} is the same markup as no prop at all', () => {
    const a = html(<PatternChart tile={tile(intraday(5))} chartOnly emaStyle="bold" axis={axis(192, 54)} />);
    const b = html(<PatternChart tile={tile(intraday(5))} chartOnly emaStyle="bold" axis={axis(192, 54)} candleLook={undefined} />);
    expect(b).toBe(a);
    expect(a).not.toContain('pc-candle-1m');
    expect(a).not.toContain('crispEdges');
  });
});
