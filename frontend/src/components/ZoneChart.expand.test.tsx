/* Expand-to-full-screen on the zone chart.
 *
 * Ajay 2026-08-17: "Can you make these charts to be full screened or something,
 * The zones are hard to figure out properly" — on SNDK five bands landed within
 * a few pixels of each other in a 340px pane.
 *
 * lightweight-charts is mocked: jsdom has no canvas, and none of what is tested
 * here is chart internals. This covers the SHELL — the control, the overlay, the
 * ways out, and the promise that the canvas actually gets the extra room.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

const series = vi.hoisted(() => ({
  setData: vi.fn(), createPriceLine: vi.fn(), attachPrimitive: vi.fn(),
  priceScale: () => ({ applyOptions: vi.fn() }),
}));

vi.mock('lightweight-charts', () => ({
  ColorType: { Solid: 'solid' },
  CrosshairMode: { Normal: 0 },
  LineStyle: { Dashed: 2, Solid: 0 },
  createChart: vi.fn(() => ({
    addCandlestickSeries: () => series,
    addLineSeries: () => series,
    addHistogramSeries: () => series,
    timeScale: () => ({ fitContent: vi.fn() }),
    subscribeCrosshairMove: vi.fn(),
    unsubscribeCrosshairMove: vi.fn(),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  })),
}));

import { ZoneChart } from './ZoneChart';
import type { ZoneMapPayload } from '../lib/zonePlan';

// The real SNDK shape that prompted the ask: bands stacked close together.
const DATA = {
  symbol: 'SNDK', name: 'Sandisk Corporation', last_price: 1641.11,
  supply_zones: [{ kind: 'supply', lo: 948, hi: 982, mid: 965, touches: 3,
                   volume: 1e6, bars_since_test: 20, strength: 60 }],
  demand_zones: [{ kind: 'demand', lo: 1485, hi: 1514, mid: 1499, touches: 3,
                   volume: 1e6, bars_since_test: 5, strength: 55 },
                 { kind: 'demand', lo: 1277, hi: 1325, mid: 1301, touches: 2,
                   volume: 1e6, bars_since_test: 30, strength: 45 }],
  nearest_resistance: null, nearest_support: null,
  in_demand_band: false, is_reentry: false, fell_from_pct: null,
  bars_since_above: null, trend_ok: true, zone_quality_ok: true,
  entry_zone: null, plan: null,
  series: Array.from({ length: 40 }, (_, i) => ({
    date: `2026-06-${String((i % 28) + 1).padStart(2, '0')}`.replace(/-(\d)$/, '-0$1'),
    open: 1500 + i, high: 1520 + i, low: 1480 + i, close: 1510 + i, volume: 1e6 + i,
  })).map((b, i) => ({ ...b, date: new Date(Date.UTC(2026, 5, 1 + i)).toISOString().slice(0, 10) })),
} as unknown as ZoneMapPayload;

const expandBtn = () => screen.getByRole('button', { name: /expand chart to full screen/i });
const canvas = (c: HTMLElement) => c.querySelector('.zonechart__canvas') as HTMLElement;

// jsdom has no ResizeObserver; the component installs one to keep the chart
// sized to its box. A no-op stand-in is enough — resizing is the library's job.
beforeEach(() => {
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver = class {
    observe() {} unobserve() {} disconnect() {}
  };
  document.body.style.overflow = '';
});
afterEach(() => { document.body.style.overflow = ''; });

describe('the expand control', () => {
  it('offers an expand button with an accessible name', () => {
    render(<ZoneChart data={DATA} />);
    expect(expandBtn()).toBeTruthy();
  });

  it('opens a modal overlay labelled for the symbol', () => {
    render(<ZoneChart data={DATA} />);
    fireEvent.click(expandBtn());
    const dlg = screen.getByRole('dialog');
    expect(dlg.getAttribute('aria-modal')).toBe('true');
    expect(dlg.getAttribute('aria-label')).toMatch(/SNDK/);
  });

  it('drops the fixed height so the canvas can take the whole viewport', () => {
    // This IS the feature: a 340px pane is what put the bands on top of each
    // other. An overlay that kept the inline height would fix nothing.
    const { container } = render(<ZoneChart data={DATA} />);
    expect(canvas(container).style.height).toBe('340px');
    fireEvent.click(expandBtn());
    expect(canvas(container).style.height).toBe('');
    expect(container.querySelector('.zonechart--full')).toBeTruthy();
  });

  it('locks the page behind it, and restores scrolling on close', () => {
    render(<ZoneChart data={DATA} />);
    fireEvent.click(expandBtn());
    expect(document.body.style.overflow).toBe('hidden');
    fireEvent.click(screen.getByRole('button', { name: /exit full screen/i }));
    expect(document.body.style.overflow).not.toBe('hidden');
  });
});

describe('every way out', () => {
  it('closes on Escape', () => {
    render(<ZoneChart data={DATA} />);
    fireEvent.click(expandBtn());
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('closes on a click of the backdrop itself', () => {
    render(<ZoneChart data={DATA} />);
    fireEvent.click(expandBtn());
    fireEvent.click(screen.getByRole('dialog'));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('does NOT close when the click lands on the chart inside it', () => {
    // Dragging the crosshair to the edge of the pane must not dismiss it.
    const { container } = render(<ZoneChart data={DATA} />);
    fireEvent.click(expandBtn());
    fireEvent.click(container.querySelector('.zonechart--full') as HTMLElement);
    expect(screen.queryByRole('dialog')).toBeTruthy();
  });

  it('says how to get out', () => {
    render(<ZoneChart data={DATA} />);
    fireEvent.click(expandBtn());
    expect(screen.getByText(/Esc to close/)).toBeTruthy();
  });
});

describe('negatives', () => {
  it('is not expanded on first render — it opens in place', () => {
    render(<ZoneChart data={DATA} />);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.body.style.overflow).not.toBe('hidden');
  });

  it('leaves no scroll lock behind when unmounted while open', () => {
    // A lock that outlives the component freezes the whole page.
    const { unmount } = render(<ZoneChart data={DATA} />);
    fireEvent.click(expandBtn());
    unmount();
    expect(document.body.style.overflow).not.toBe('hidden');
  });

  it('ignores Escape when it is not open', () => {
    render(<ZoneChart data={DATA} />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders the too-short message without an expand button', () => {
    // Nothing to enlarge, so offering the control would be a dead end.
    render(<ZoneChart data={{ ...DATA, series: [] } as unknown as ZoneMapPayload} />);
    expect(screen.getByText(/Not enough history/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /expand/i })).toBeNull();
  });
});
