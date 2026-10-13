import { describe, it, expect, afterEach } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import type { CmBar, CmTile } from '../lib/chartMaps';
import type { ServedVolAvg } from '../lib/volumePane';

/* 📊 PatternChart draws the backend's full-frame 50-bar volume average when
 * the tile carries `vol_avg` (2026-10-13), and its own SMA otherwise. */

const bars = (n: number): CmBar[] =>
  Array.from({ length: n }, (_, i) => {
    const c = 10 + i * 0.1;
    const o = i % 2 ? c + 0.05 : c - 0.05;
    const t = new Date(Date.UTC(2026, 3, 1) + i * 86_400_000).toISOString().slice(0, 10);
    return { t, o, h: c + 0.3, l: c - 0.4, c, v: 1000 + i * 10 } as CmBar;
  });

const tile = (b: CmBar[], vol_avg?: ServedVolAvg | null): CmTile => ({
  symbol: 'VOLT', href: '/sepa/VOLT', bars: b, bands: [], lines: [], markers: [],
  stats: [], why: '', ...(vol_avg !== undefined ? { vol_avg } : {}),
} as CmTile);

const draw = (t: CmTile) => render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);
const smaPaths = (c: HTMLElement) => Array.from(c.querySelectorAll('svg.cm-svg path.pc-vol-sma'));
const points = (p: Element) => (p.getAttribute('d') || '').split('L').length;

afterEach(() => cleanup());

describe('PatternChart — served volume average', () => {
  it('40 bars + a served average: one solid line from bar 0, no flat fallback', () => {
    const b = bars(40);
    const { container } = draw(tile(b, { period: 50, label: '50-bar avg volume',
                                          values: b.map(() => 1100) }));
    const p = smaPaths(container);
    expect(p).toHaveLength(1);
    expect(p[0].getAttribute('class')).not.toContain('pc-vol-sma-flat');
    expect(points(p[0])).toBe(40);
    expect(p[0].querySelector('title')!.textContent).toBe('50-bar simple average volume');
    expect(container.innerHTML).not.toMatch(/NaN/);
  });

  it('60 bars: the served line has 60 points where the fallback has 11', () => {
    const b = bars(60);
    const s = draw(tile(b, { period: 50, label: 'x', values: b.map((x) => x.v as number) })).container;
    expect(points(smaPaths(s)[0])).toBe(60);
    cleanup();
    const f = draw(tile(b)).container;
    expect(points(smaPaths(f)[0])).toBe(11);
  });

  it('a served gap splits the line (a live bar the frame lacked)', () => {
    const b = bars(30);
    const values: (number | null)[] = b.map(() => 1200);
    values[29] = null;
    const { container } = draw(tile(b, { period: 50, label: 'x', values }));
    const p = smaPaths(container);
    expect(p).toHaveLength(1);
    expect(points(p[0])).toBe(29);
  });

  it('a served average above every shown bar stays inside the pane and the scale says so', () => {
    const b = bars(30);                                       // tallest bar 1,290
    const { container } = draw(tile(b, { period: 50, label: 'x', values: b.map(() => 5000) }));
    const d = smaPaths(container)[0].getAttribute('d') || '';
    const ys = d.replace(/^M/, '').split(' L').map((pt) => Number(pt.split(',')[1]));
    const volTop = 180 - Math.round(190 * 0.22);
    for (const y of ys) expect(y).toBeGreaterThanOrEqual(volTop - 0.001);
    expect(container.querySelector('.pc-vol-max')!.textContent).toBe('5K');
  });

  it('the pane title names the same scale top the corner label prints', () => {
    const b = bars(30);                                       // tallest bar 1,290
    const { container } = draw(tile(b, { period: 50, label: 'x', values: b.map(() => 5000) }));
    const pane = container.querySelector('.pc-vol-pane > title')!.textContent || '';
    expect(pane).toBe('50-bar simple average volume · scale top 5K · tallest bar 1K');
    expect(pane).toContain(container.querySelector('.pc-vol-max')!.textContent!);
  });

  it('NEGATIVE: with the tallest bar on top the title stays "tallest bar" only', () => {
    const b = bars(60);
    const { container } = draw(tile(b, { period: 50, label: 'x', values: b.map(() => 500) }));
    const pane = container.querySelector('.pc-vol-pane > title')!.textContent || '';
    expect(pane).toBe('50-bar simple average volume · tallest bar 2K');
    expect(pane).not.toContain('scale top');
    expect(container.querySelector('.pc-vol-max')!.textContent).toBe('2K');
  });

  // --- negatives: the shipped pane, unchanged ---
  it('NEGATIVE: 30 bars and no served average → the shipped flat dashed fallback', () => {
    const { container } = draw(tile(bars(30)));
    const p = smaPaths(container);
    expect(p).toHaveLength(1);
    expect(p[0].getAttribute('class')).toContain('pc-vol-sma-flat');
  });

  it('NEGATIVE: a served line of the wrong length is ignored (fallback drawn)', () => {
    const b = bars(60);
    const { container } = draw(tile(b, { period: 50, label: 'x', values: [1, 2, 3] }));
    expect(points(smaPaths(container)[0])).toBe(11);
    expect(container.querySelector('.pc-vol-max')!.textContent).toBe('2K');
  });

  it('NEGATIVE: a served line with ONE finite point → the shipped flat dashed fallback', () => {
    const b = bars(30);
    const values: (number | null)[] = b.map(() => null);
    values[29] = 9000;                                        // above every bar
    const { container } = draw(tile(b, { period: 50, label: 'x', values }));
    const p = smaPaths(container);
    expect(p).toHaveLength(1);
    expect(p[0].getAttribute('class')).toContain('pc-vol-sma-flat');
    expect(p[0].querySelector('title')!.textContent)
      .toBe('average volume over 30 bars (only 30 bars on this chart; 50 wanted)');
    expect(container.querySelector('.pc-vol-max')!.textContent).toBe('1K');
    expect(container.querySelector('.pc-vol-pane > title')!.textContent)
      .not.toContain('average not drawn');
  });

  it('NEGATIVE: vol_avg null → fallback, no NaN', () => {
    const { container } = draw(tile(bars(60), null));
    expect(points(smaPaths(container)[0])).toBe(11);
    expect(container.innerHTML).not.toMatch(/NaN/);
  });

  it('NEGATIVE: a served average on a tile with no volume draws no pane at all', () => {
    const b = bars(40).map((x) => ({ ...x, v: 0 }));
    const { container } = draw(tile(b, { period: 50, label: 'x', values: b.map(() => 1000) }));
    expect(container.querySelector('.pc-vol-pane')).toBeNull();
    expect(smaPaths(container)).toHaveLength(0);
  });
});
