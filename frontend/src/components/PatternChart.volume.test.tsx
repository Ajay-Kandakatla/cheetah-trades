import { describe, it, expect, afterEach } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import type { CmBar, CmTile } from '../lib/chartMaps';
import { VOL_DOWN, VOL_UP, VOLUME_SMA_COLOR } from '../lib/volumePane';

/* 📊 The volume pane on the Chart Maps tile (Ajay 2026-10-13: "show me volume
 * on our charts please ... green and red volume"). One column per bar, coloured
 * by the candle above it, plus the thin 50-bar average; a tile without `v`
 * draws no pane and exactly the old chart. */

const bars = (n: number, withV = true): CmBar[] =>
  Array.from({ length: n }, (_, i) => {
    const c = 10 + i * 0.1;
    // even bars up (close > open), odd bars down; bar 3 a doji
    const o = i === 3 ? c : i % 2 ? c + 0.05 : c - 0.05;
    const t = new Date(Date.UTC(2026, 3, 1) + i * 86_400_000).toISOString().slice(0, 10);
    const b: any = { t, o, h: c + 0.3, l: c - 0.4, c };
    if (withV) b.v = 1000 + i * 10;
    return b as CmBar;
  });

const tile = (b: CmBar[]): CmTile => ({
  symbol: 'VOLT', href: '/sepa/VOLT', bars: b, bands: [], lines: [], markers: [],
  stats: [], why: '',
});

const draw = (t: CmTile, height?: number) =>
  render(<MemoryRouter><PatternChart tile={t} height={height} /></MemoryRouter>);

const volRects = (c: HTMLElement) => Array.from(c.querySelectorAll('svg.cm-svg rect.pc-vol'));
const candleBodies = (c: HTMLElement) =>
  Array.from(c.querySelectorAll('svg.cm-svg g[opacity] > rect'));

afterEach(() => cleanup());

describe('PatternChart — 📊 volume pane', () => {
  it('draws one column per bar, green for up / doji bars and red for down bars', () => {
    const b = bars(60);
    const { container } = draw(tile(b));
    const rects = volRects(container);
    expect(rects).toHaveLength(60);
    rects.forEach((r, i) => {
      const want = b[i].c >= b[i].o ? VOL_UP : VOL_DOWN;
      expect(r.getAttribute('fill')).toBe(want);
    });
    expect(rects[3].getAttribute('fill')).toBe(VOL_UP);   // the doji
    expect(rects[1].getAttribute('fill')).toBe(VOL_DOWN);
  });

  it('the tallest bar reaches the pane top; every column stands on the pane floor', () => {
    const { container } = draw(tile(bars(60)));
    const rects = volRects(container);
    const bottoms = rects.map((r) => Number(r.getAttribute('y')) + Number(r.getAttribute('height')));
    for (const y of bottoms) expect(y).toBeCloseTo(180, 6);
    const tops = rects.map((r) => Number(r.getAttribute('y')));
    expect(Math.min(...tops)).toBeCloseTo(180 - Math.round(190 * 0.22), 6);
    for (const r of rects) expect(Number(r.getAttribute('width'))).toBeGreaterThanOrEqual(1.4);
  });

  it('draws the 50-bar average as a thin grey line starting at bar 50', () => {
    const { container } = draw(tile(bars(60)));
    const sma = container.querySelectorAll('svg.cm-svg path.pc-vol-sma');
    expect(sma).toHaveLength(1);
    expect(sma[0].getAttribute('stroke')).toBe(VOLUME_SMA_COLOR);
    expect(sma[0].getAttribute('stroke-width')).toBe('1');
    // 11 points: bars 49..59
    expect((sma[0].getAttribute('d') || '').split('L')).toHaveLength(11);
    expect(sma[0].querySelector('title')!.textContent).toBe('50-bar simple average volume');
    expect(container.querySelector('.pc-vol-max')!.textContent).toBe('2K');
  });

  it('fewer than 50 bars: the average spans the bars it has and the title says so', () => {
    const { container } = draw(tile(bars(30)));
    const sma = container.querySelectorAll('svg.cm-svg path.pc-vol-sma');
    expect(sma).toHaveLength(1);
    expect(sma[0].getAttribute('class')).toContain('pc-vol-sma-flat');
    expect(sma[0].querySelector('title')!.textContent)
      .toContain('only 30 bars on this chart; 50 wanted');
  });

  it('the candles move up into the shorter price pane but stay inside the SVG, above the volume', () => {
    const withV = draw(tile(bars(60))).container;
    const yV = candleBodies(withV).map((r) => Number(r.getAttribute('y')) + Number(r.getAttribute('height')));
    cleanup();
    const noV = draw(tile(bars(60, false))).container;
    const yN = candleBodies(noV).map((r) => Number(r.getAttribute('y')) + Number(r.getAttribute('height')));
    expect(yV).toHaveLength(60);
    expect(yN).toHaveLength(60);
    // the lowest body bottom is higher with the pane (smaller y) …
    expect(Math.max(...yV)).toBeLessThan(Math.max(...yN));
    // … and every body sits inside the SVG and above the volume pane
    const volTop = 180 - Math.round(190 * 0.22);
    for (const y of yV) {
      expect(y).toBeGreaterThan(0);
      expect(y).toBeLessThan(volTop);
    }
  });

  it('hovering a bar still reads its volume in the HUD; no price chip over the volume pane', () => {
    const { container } = draw(tile(bars(60)));
    const svg = container.querySelector('svg')!;
    svg.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 620, height: 190, right: 620, bottom: 190, x: 0, y: 0,
      toJSON: () => ({}),
    }) as DOMRect;
    fireEvent.mouseMove(svg, { clientX: 300, clientY: 170 });   // inside the volume pane
    expect(container.textContent).toMatch(/Vol \d/);
    expect(container.querySelectorAll('rect[rx="2.5"]')).toHaveLength(0);
    expect(container.innerHTML).not.toMatch(/NaN/);
    fireEvent.mouseMove(svg, { clientX: 300, clientY: 60 });    // over price
    expect(container.querySelectorAll('rect[rx="2.5"]')).toHaveLength(1);
  });

  // --- negatives ---
  it('NEGATIVE: bars with no `v` → no pane, no average, no NaN anywhere', () => {
    const { container } = draw(tile(bars(60, false)));
    expect(volRects(container)).toHaveLength(0);
    expect(container.querySelector('.pc-vol-pane')).toBeNull();
    expect(container.querySelector('.pc-vol-sma')).toBeNull();
    expect(container.innerHTML).not.toMatch(/NaN|undefined/);
    // the price pane keeps the whole tile (old drawing)
    expect(container.querySelector('svg')!.getAttribute('viewBox')).toBe('0 0 620 190');
  });

  it('NEGATIVE: all-zero volume draws no pane', () => {
    const b = bars(60).map((x) => ({ ...x, v: 0 }));
    const { container } = draw(tile(b));
    expect(container.querySelector('.pc-vol-pane')).toBeNull();
  });

  it('NEGATIVE: a junk volume on one bar skips that column and gaps the line, no NaN', () => {
    const b = bars(70);
    (b[55] as any).v = NaN;
    (b[56] as any).v = -4;
    (b[57] as any).v = undefined;
    const { container } = draw(tile(b));
    expect(volRects(container)).toHaveLength(67);
    // bars 55-57 hole: windows ending 55..106 hold it, so only 49..54 draw
    const sma = Array.from(container.querySelectorAll('path.pc-vol-sma'));
    expect(sma).toHaveLength(1);
    expect((sma[0].getAttribute('d') || '').split('L')).toHaveLength(6);
    expect(container.innerHTML).not.toMatch(/NaN/);
  });

  it('the volume pane paints FIRST: a BUY tag rect follows g.pc-vol-pane in document order', () => {
    const b = bars(60);
    const { container } = draw({ ...tile(b), markers: [{ date: b[40].t, kind: 'buy', label: 'BUY' }] });
    const pane = container.querySelector('g.pc-vol-pane')!;
    const tag = Array.from(container.querySelectorAll('svg.cm-svg text'))
      .find((t) => t.textContent === 'BUY')!;
    expect(pane).not.toBeNull();
    expect(tag).toBeTruthy();
    const rect = tag.parentElement!.querySelector('rect')!;
    expect(rect.getAttribute('rx')).toBe('2.5');
    expect(pane.compareDocumentPosition(rect) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(pane.contains(rect)).toBe(false);
  });

  it('NEGATIVE: 60 bars, bar 50 has no volume → one lone average point → nothing flat, no full-window claim', () => {
    const b = bars(60);
    (b[50] as any).v = null;
    const { container } = draw(tile(b));
    expect(container.querySelector('.pc-vol-pane')).not.toBeNull();
    expect(container.querySelector('.pc-vol-sma-flat')).toBeNull();
    expect(container.querySelector('path.pc-vol-sma')).toBeNull();
    const titles = Array.from(container.querySelectorAll('.pc-vol-pane title')).map((t) => t.textContent || '');
    expect(titles.length).toBeGreaterThan(0);
    for (const t of titles) {
      expect(t).not.toMatch(/simple average/);
      expect(t).not.toMatch(/average volume over/);
    }
    expect(container.innerHTML).not.toMatch(/NaN/);
  });
});

