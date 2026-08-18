/* The plan labels are ours now, not the library's.
 *
 * Ajay 2026-08-17: "Can you move these labels to the left or something they
 * are all clumsy and its hard to look at the bars".
 *
 * What these pin is the WIRING, which is where this change can silently
 * regress: the library's own plate must stay switched off, the axis chip must
 * stay on, and a blank right margin must be reserved for the plates to sit in.
 * The drawing itself is canvas and jsdom has none; the arithmetic behind it is
 * covered in lib/labelLayout.test.ts and lib/zoneChart.test.ts.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';

const series = vi.hoisted(() => ({
  setData: vi.fn(), createPriceLine: vi.fn(), attachPrimitive: vi.fn(),
  priceScale: () => ({ applyOptions: vi.fn() }),
}));
const chart = vi.hoisted(() => ({
  addCandlestickSeries: vi.fn(), addLineSeries: vi.fn(), addHistogramSeries: vi.fn(),
  timeScale: vi.fn(), subscribeCrosshairMove: vi.fn(), unsubscribeCrosshairMove: vi.fn(),
  applyOptions: vi.fn(), remove: vi.fn(),
}));
const fitContent = vi.hoisted(() => vi.fn());

vi.mock('lightweight-charts', () => ({
  ColorType: { Solid: 'solid' },
  CrosshairMode: { Normal: 0 },
  LineStyle: { Dashed: 2, Solid: 0 },
  createChart: vi.fn(() => chart),
}));

import { ZoneChart } from './ZoneChart';
import { PlanLabelsPrimitive } from './planLabelsPrimitive';
import { ZoneBandsPrimitive } from './zoneBandsPrimitive';
import type { ZoneMapPayload } from '../lib/zonePlan';

const bars = (n: number) => Array.from({ length: n }, (_, i) => {
  const d = new Date(Date.UTC(2026, 0, 1 + i)).toISOString().slice(0, 10);
  const c = 64 + Math.sin(i / 7) * 3;
  return { date: d, open: c, high: c + 1, low: c - 1, close: c, volume: 1e6 };
});

const DATA = {
  symbol: 'MOS', name: 'Mosaic', last_price: 64.40,
  supply_zones: [], demand_zones: [{ kind: 'demand', lo: 64.41, hi: 66.08, mid: 65.2,
                                     touches: 3, volume: 1e6, bars_since_test: 4, strength: 60 }],
  nearest_resistance: null, nearest_support: null,
  in_demand_band: true, is_reentry: true, fell_from_pct: 9, bars_since_above: 6,
  trend_ok: true, zone_quality_ok: true, zone_broken: false,
  entry_zone: { kind: 'demand', lo: 64.41, hi: 66.08, mid: 65.2, touches: 3,
                volume: 1e6, bars_since_test: 4, strength: 60 },
  plan: { entry_low: 64.41, entry_high: 66.08, entry_ref: 66.08, stop: 63.44,
          risk_pct: 4.0, target: 70.88, reward_pct: 7.3, rr: 1.8,
          risk_exceeds_max: false, max_stop_pct: 10, stop_recently_hit: true },
  series: bars(140),
} as unknown as ZoneMapPayload;

beforeEach(() => {
  vi.clearAllMocks();
  chart.addCandlestickSeries.mockReturnValue(series);
  chart.addLineSeries.mockReturnValue(series);
  chart.addHistogramSeries.mockReturnValue(series);
  chart.timeScale.mockReturnValue({ fitContent });
  // jsdom reports 0 for every layout box; the gutter is width-derived.
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(760);
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(340);
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver =
    class { observe() {} disconnect() {} };
});

const draw = () => render(<ZoneChart data={DATA} />);

describe('the library no longer draws the plan labels', () => {
  it('creates every price line with an EMPTY title', () => {
    // `showPaneLabel = options.title !== ''` in lightweight-charts 4.2.3 — an
    // empty title is precisely the switch that removes the clumsy box, and it
    // removes nothing else.
    draw();
    expect(series.createPriceLine).toHaveBeenCalled();
    for (const [opts] of series.createPriceLine.mock.calls) {
      expect(opts.title).toBe('');
    }
  });

  it('keeps the axis chip, which is now the only price the library prints', () => {
    draw();
    for (const [opts] of series.createPriceLine.mock.calls) {
      expect(opts.axisLabelVisible).toBe(true);
    }
  });

  it('still draws a rule for every level', () => {
    // The lines are not the complaint; only their labels were.
    draw();
    expect(series.createPriceLine.mock.calls.map(([o]) => o.price).sort((a, b) => a - b))
      .toEqual([63.44, 64.40, 66.08, 70.88]);
  });

  it('attaches our own label primitive on top of the bands', () => {
    draw();
    const kinds = series.attachPrimitive.mock.calls.map(([p]) => p.constructor);
    expect(kinds).toContain(ZoneBandsPrimitive);
    expect(kinds).toContain(PlanLabelsPrimitive);
  });

  it('hands the primitive the same specs the price lines were built from', () => {
    draw();
    const prim = series.attachPrimitive.mock.calls
      .map(([p]) => p).find((p) => p instanceof PlanLabelsPrimitive)!;
    expect(prim.lines.map((l: { kind: string }) => l.kind).sort())
      .toEqual(['buy', 'now', 'stop', 'target']);
    // The titles the LIBRARY no longer prints have to survive here, or the
    // change deletes the labels instead of moving them.
    expect(prim.lines.every((l: { title: string }) => /\$\d/.test(l.title))).toBe(true);
  });
});

describe('nothing is drawn twice', () => {
  it('silences the series own last-price rule AND its axis chip', () => {
    // Both default to true, and both duplicated our NOW line: two rules at one
    // price and two chips reading 64.40. Confirmed in a browser before this was
    // written. TWO flags — priceLineVisible removes only the rule.
    draw();
    const opts = chart.addCandlestickSeries.mock.calls[0][0];
    expect(opts.priceLineVisible).toBe(false);
    expect(opts.lastValueVisible).toBe(false);
  });

  it('silences the volume series own last value too', () => {
    // Volume's chip lands in the same stack as the plan's prices reading
    // "9.78M", and its rule crosses the bands. The HUD already reports volume.
    draw();
    const opts = chart.addHistogramSeries.mock.calls[0][0];
    expect(opts.priceLineVisible).toBe(false);
    expect(opts.lastValueVisible).toBe(false);
  });

  it('applies the same silence to the fallback line series', () => {
    // An older cached payload draws a line, not candles — and would otherwise
    // keep the duplicate that the candlestick path just lost.
    render(<ZoneChart data={{ ...DATA,
      series: DATA.series!.map((b) => ({ date: b.date, close: b.close })) } as never} />);
    const opts = chart.addLineSeries.mock.calls[0][0];
    expect(opts.priceLineVisible).toBe(false);
    expect(opts.lastValueVisible).toBe(false);
  });
});

describe('the blank gutter the plates sit in', () => {
  it('reserves right-hand bar slots so plates do not land on the newest candles', () => {
    // This is the actual fix for "hard to look at the bars": fitContent() puts
    // the last candle flush against the axis, leaving the plates nowhere to go.
    draw();
    const offsets = chart.applyOptions.mock.calls
      .map(([o]) => o?.timeScale?.rightOffset).filter((v) => v !== undefined);
    expect(offsets.length).toBeGreaterThan(0);
    expect(offsets[0]).toBeGreaterThan(0);
  });

  it('still calls fitContent, which is what applies the offset', () => {
    // Verified in the library source: _internal_fitContent sets the visible
    // range to (first, last + rightOffset). Drop this call and the gutter
    // silently never appears.
    draw();
    expect(fitContent).toHaveBeenCalled();
  });

  // --- negatives ---

  it('asks for no gutter when the pane has not been measured yet', () => {
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(0);
    draw();
    const offsets = chart.applyOptions.mock.calls
      .map(([o]) => o?.timeScale?.rightOffset).filter((v) => v !== undefined);
    expect(offsets.every((v) => v === 0)).toBe(true);
  });

  it('does not crash a payload that has no plan to label', () => {
    const bare = { ...DATA, plan: null, entry_zone: null } as unknown as ZoneMapPayload;
    expect(() => render(<ZoneChart data={bare} />)).not.toThrow();
  });
});
