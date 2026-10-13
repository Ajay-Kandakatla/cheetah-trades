import { describe, it, expect, afterEach, beforeAll, vi } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { IntradayChart } from './IntradayChart';
import type { DayBars, IntradayBar } from '../hooks/useDayTrading';
import { VOL_DOWN, VOL_UP, VOLUME_SMA_COLOR, volumePaneLayout } from '../lib/volumePane';

/* 📊 The volume pane on the Day-trading / Scalping chart (Ajay 2026-10-13:
 * "show me volume on our charts please ... green and red volume"). Mirrors
 * PatternChart.volume.test.tsx: one column per bar coloured by its candle, the
 * thin 50-bar average, the price on the shorter pane, a frame without `v`
 * draws exactly the old chart. */

beforeAll(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
});
afterEach(() => cleanup());

const H = 420;                                   // the component's default height
const PAD_B = 30;
const PANE = volumePaneLayout(H, PAD_B, true);   // volBot 390, volTop 298

const bars = (n: number, withV = true): IntradayBar[] =>
  Array.from({ length: n }, (_, i) => {
    const c = 100 + i * 0.05;
    // even bars up, odd bars down; bar 3 a doji
    const o = i === 3 ? c : i % 2 ? c + 0.03 : c - 0.03;
    const ts = new Date(Date.UTC(2026, 9, 13, 13, 30) + i * 60_000).toISOString().slice(0, 19);
    const b: any = { ts, o, h: c + 0.1, l: c - 0.1, c, session: 'rth', vwap: c, atr14: 0.2 };
    if (withV) b.v = 1000 + i * 10;
    return b as IntradayBar;
  });

const frame = (b: IntradayBar[]): DayBars => ({ symbol: 'VOLT', bars: b, indicators: {} });

const draw = (b: IntradayBar[]) => render(<IntradayChart data={frame(b)} />);
const volRects = (c: HTMLElement) => Array.from(c.querySelectorAll('svg rect.day-chart__vol'));
const bodies = (c: HTMLElement) => Array.from(c.querySelectorAll('svg rect.day-chart__body'));

describe('IntradayChart — 📊 volume pane', () => {
  it('one column per bar: green for up / doji bars, red for down bars', () => {
    const b = bars(60);
    const { container } = draw(b);
    const rects = volRects(container);
    expect(rects).toHaveLength(60);
    rects.forEach((r, i) => {
      expect(r.getAttribute('fill')).toBe(b[i].c >= b[i].o ? VOL_UP : VOL_DOWN);
    });
    expect(rects[3].getAttribute('fill')).toBe(VOL_UP);   // the doji
    expect(rects[1].getAttribute('fill')).toBe(VOL_DOWN);
  });

  it('the pane is the bottom ~22%: columns stand on its floor, the tallest reaches its top', () => {
    const { container } = draw(bars(60));
    const rects = volRects(container);
    for (const r of rects) {
      expect(Number(r.getAttribute('y')) + Number(r.getAttribute('height'))).toBeCloseTo(PANE.volBot, 6);
    }
    expect(Math.min(...rects.map((r) => Number(r.getAttribute('y'))))).toBeCloseTo(PANE.volTop, 6);
    expect(PANE.volBot - PANE.volTop).toBe(Math.round(H * 0.22));
  });

  it('the 50-bar average is a thin grey line from bar 50, over the full frame', () => {
    const { container } = draw(bars(60));
    const sma = container.querySelectorAll('svg path.day-chart__vol-sma');
    expect(sma).toHaveLength(1);
    expect(sma[0].getAttribute('stroke')).toBe(VOLUME_SMA_COLOR);
    expect(sma[0].getAttribute('stroke-width')).toBe('1');
    expect((sma[0].getAttribute('d') || '').split('L')).toHaveLength(11);   // bars 49..59
    expect(sma[0].querySelector('title')!.textContent).toBe('50-bar simple average volume');
  });

  it('fewer than 50 bars: the average is flat + dashed and its title says so', () => {
    const { container } = draw(bars(30));
    const sma = container.querySelectorAll('svg path.day-chart__vol-sma');
    expect(sma).toHaveLength(1);
    expect(sma[0].getAttribute('class')).toContain('day-chart__vol-sma-flat');
    expect(sma[0].querySelector('title')!.textContent).toContain('only 30 bars on this chart; 50 wanted');
  });

  it('candles move into the shorter price pane and stay above the volume', () => {
    const yV = bodies(draw(bars(60)).container)
      .map((r) => Number(r.getAttribute('y')) + Number(r.getAttribute('height')));
    cleanup();
    const yN = bodies(draw(bars(60, false)).container)
      .map((r) => Number(r.getAttribute('y')) + Number(r.getAttribute('height')));
    expect(yV).toHaveLength(60);
    expect(Math.max(...yV)).toBeLessThan(Math.max(...yN));
    for (const y of yV) expect(y).toBeLessThan(PANE.volTop);
  });

  it('hover still shows the bar tooltip with V; no price pill over the volume pane', () => {
    const { container } = draw(bars(60));
    const svg = container.querySelector('svg')!;
    svg.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 900, height: H, right: 900, bottom: H, x: 0, y: 0, toJSON: () => ({}),
    }) as DOMRect;
    fireEvent.mouseMove(svg, { clientX: 400, clientY: 360 });     // inside the volume pane
    expect(container.querySelector('.day-chart__tooltip')).not.toBeNull();
    expect(container.querySelector('.day-chart__tooltip')!.textContent).toMatch(/V\d/);
    expect(container.querySelector('.day-chart__hover-pill')).toBeNull();
    fireEvent.mouseMove(svg, { clientX: 400, clientY: 100 });     // over price
    expect(container.querySelector('.day-chart__hover-pill')).not.toBeNull();
    expect(container.innerHTML).not.toMatch(/NaN/);
  });

  // --- negatives ---
  it('NEGATIVE: bars with no `v` → no pane, no average, old price height, no NaN', () => {
    const { container } = draw(bars(60, false));
    expect(container.querySelector('.day-chart__vol-pane')).toBeNull();
    expect(volRects(container)).toHaveLength(0);
    expect(container.querySelector('.day-chart__vol-sma')).toBeNull();
    // the RTH shading keeps the old full price height (420 - 14 - 30)
    expect(container.querySelector('rect.day-chart__rth-band')!.getAttribute('height')).toBe('376');
    expect(container.innerHTML).not.toMatch(/NaN|undefined/);
  });

  it('NEGATIVE: hovering a bar with no `v` reads "—", never NaN, and does not throw', () => {
    const { container } = draw(bars(60, false));
    const svg = container.querySelector('svg')!;
    svg.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 900, height: H, right: 900, bottom: H, x: 0, y: 0, toJSON: () => ({}),
    }) as DOMRect;
    fireEvent.mouseMove(svg, { clientX: 400, clientY: 100 });
    expect(container.querySelector('.day-chart__tooltip')!.textContent).toContain('V—');
    expect(container.innerHTML).not.toMatch(/NaN/);
  });

  it('NEGATIVE: all-zero volume draws no pane', () => {
    const { container } = draw(bars(60).map((b) => ({ ...b, v: 0 })));
    expect(container.querySelector('.day-chart__vol-pane')).toBeNull();
  });

  it('NEGATIVE: junk volume on three bars skips those columns and gaps the line, no NaN', () => {
    const b = bars(70);
    (b[55] as any).v = NaN;
    (b[56] as any).v = -4;
    (b[57] as any).v = undefined;
    const { container } = draw(b);
    expect(volRects(container)).toHaveLength(67);
    const sma = Array.from(container.querySelectorAll('path.day-chart__vol-sma'));
    expect(sma).toHaveLength(1);
    expect((sma[0].getAttribute('d') || '').split('L')).toHaveLength(6);   // bars 49..54
    expect(container.innerHTML).not.toMatch(/NaN/);
  });

  it('NEGATIVE: 60 bars, bar 50 has no volume → one lone average point → nothing flat, no full-window claim', () => {
    const b = bars(60);
    (b[50] as any).v = null;
    const { container } = draw(b);
    expect(container.querySelector('.day-chart__vol-pane')).not.toBeNull();
    expect(container.querySelector('.day-chart__vol-sma')).toBeNull();
    for (const t of Array.from(container.querySelectorAll('.day-chart__vol-pane title'))) {
      expect(t.textContent || '').not.toMatch(/simple average|average volume over/);
    }
    expect(container.innerHTML).not.toMatch(/NaN/);
  });
});
