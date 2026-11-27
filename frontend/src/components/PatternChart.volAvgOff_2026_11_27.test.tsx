import { describe, it, expect, afterEach } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import type { CmBar, CmTile } from '../lib/chartMaps';
import { shortVol } from '../lib/chartMaps';
import type { ServedVolAvg } from '../lib/volumePane';

/* 👀 2026-11-27 (Ajay: "not sure what the line on volume is its blocking my story"): PatternChart's opt-in
 * `volAvg={false}` drops the 50-bar average line from the volume pane and scales the pane to the tallest bar.
 * Absent / `true` → the shipped pane, byte-identical. */

const bars = (n: number, withV = true): CmBar[] =>
  Array.from({ length: n }, (_, i) => {
    const c = 10 + i * 0.1;
    const o = i % 2 ? c + 0.05 : c - 0.05;
    const t = new Date(Date.UTC(2026, 3, 1) + i * 86_400_000).toISOString().slice(0, 10);
    const b: any = { t, o, h: c + 0.3, l: c - 0.4, c };
    if (withV) b.v = 1000 + i * 10;
    return b as CmBar;
  });

const tile = (b: CmBar[], vol_avg?: ServedVolAvg | null): CmTile => ({
  symbol: 'VOLT', href: '/sepa/VOLT', bars: b, bands: [], lines: [], markers: [],
  stats: [], why: '', ...(vol_avg !== undefined ? { vol_avg } : {}),
} as CmTile);

const draw = (t: CmTile, volAvg?: boolean) =>
  render(<MemoryRouter>
    {volAvg === undefined ? <PatternChart tile={t} /> : <PatternChart tile={t} volAvg={volAvg} />}
  </MemoryRouter>).container;
const sma = (c: HTMLElement) => c.querySelectorAll('svg.cm-svg path.pc-vol-sma');
const rects = (c: HTMLElement) => Array.from(c.querySelectorAll('svg.cm-svg rect.pc-vol'));
const dataVols = (c: HTMLElement) => rects(c).map((r) => r.getAttribute('data-vol'));
const paneTitle = (c: HTMLElement) => c.querySelector('.pc-vol-pane > title')!.textContent;
const VOL_TOP = 180 - Math.round(190 * 0.22);

afterEach(() => cleanup());

describe('PatternChart — volAvg={false} (2026-11-27)', () => {
  it('a served average above every bar: no line, same columns, scale = the tallest bar', () => {
    const b = bars(30);                                       // tallest bar 1,290
    const served = { period: 50, label: 'x', values: b.map(() => 5000) };
    const on = draw(tile(b, served));
    const onVols = dataVols(on);
    expect(sma(on).length).toBe(1);
    expect(on.querySelector('.pc-vol-max')!.textContent).toBe('5K');
    cleanup();
    const off = draw(tile(b, served), false);
    expect(sma(off)).toHaveLength(0);
    expect(rects(off)).toHaveLength(30);
    expect(dataVols(off)).toEqual(onVols);
    expect(off.querySelector('.pc-vol-max')!.textContent).toBe(shortVol(1290));
    expect(paneTitle(off)).toBe(`volume · tallest bar ${shortVol(1290)}`);
    expect(paneTitle(off)).not.toContain('scale top');
    expect(paneTitle(off)).not.toContain('average');
    // the tallest column reaches the pane top (never squashed under a served line)
    const tallest = rects(off).find((r) => r.getAttribute('data-vol') === '1290')!;
    expect(Number(tallest.getAttribute('y'))).toBeCloseTo(VOL_TOP, 6);
    expect(off.innerHTML).not.toMatch(/NaN/);
  });

  it('< 50 bars and no served average → no flat dashed line either', () => {
    const on = draw(tile(bars(30)));
    expect(on.querySelectorAll('path.pc-vol-sma-flat')).toHaveLength(1);
    cleanup();
    const off = draw(tile(bars(30)), false);
    expect(sma(off)).toHaveLength(0);
    expect(off.querySelectorAll('path.pc-vol-sma-flat')).toHaveLength(0);
    expect(rects(off)).toHaveLength(30);
    expect(paneTitle(off)).toBe(`volume · tallest bar ${shortVol(1290)}`);
  });

  it('60 bars, own SMA: the line is gone, the columns are unchanged', () => {
    const on = draw(tile(bars(60)));
    const onRects = rects(on).map((r) => r.outerHTML);
    expect(sma(on).length).toBeGreaterThan(0);
    cleanup();
    const off = draw(tile(bars(60)), false);
    expect(sma(off)).toHaveLength(0);
    expect(rects(off).map((r) => r.outerHTML)).toEqual(onRects);
    expect(off.querySelector('.pc-vol-max')!.textContent).toBe(shortVol(1590));
  });

  // --- negatives ---
  it('NEGATIVE: prop absent and volAvg={true} → identical HTML, line present', () => {
    for (const t of [tile(bars(30)), tile(bars(60)),
                     tile(bars(30), { period: 50, label: 'x', values: bars(30).map(() => 5000) })]) {
      const a = draw(t).innerHTML;
      cleanup();
      const c = draw(t, true);
      expect(c.innerHTML).toBe(a);
      expect(sma(c).length).toBeGreaterThan(0);
      cleanup();
    }
  });

  it('NEGATIVE: volAvg={false} on a tile with no volume → no pane at all', () => {
    const c = draw(tile(bars(40, false)), false);
    expect(c.querySelector('.pc-vol-pane')).toBeNull();
    expect(rects(c)).toHaveLength(0);
    expect(sma(c)).toHaveLength(0);
  });

  it('NEGATIVE: no-volume tile → the price pane HTML is identical with and without the prop', () => {
    const t = tile(bars(40, false), { period: 50, label: 'x', values: bars(40).map(() => 1000) });
    const a = draw(t).innerHTML;
    cleanup();
    expect(draw(t, false).innerHTML).toBe(a);
  });

  it('NEGATIVE: volAvg={false} with volume leaves everything outside the pane untouched', () => {
    const strip = (c: HTMLElement) => {
      const svg = c.querySelector('svg.cm-svg')!.cloneNode(true) as SVGElement;
      svg.querySelector('.pc-vol-pane')?.remove();
      return svg.outerHTML;
    };
    const on = strip(draw(tile(bars(60))));
    cleanup();
    expect(strip(draw(tile(bars(60)), false))).toBe(on);
  });
});
