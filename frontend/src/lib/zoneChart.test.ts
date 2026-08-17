/* Every number the candlestick zone chart derives.
 *
 * Ajay 2026-08-16: "I wanna be able to hover on the pricing at for some points"
 * and "can you also add volume please".
 *
 * The component is wiring; this is the arithmetic. Fixtures are real bars from
 * the HASI zone-map payload the day he asked.
 */
import { describe, expect, it } from 'vitest';
import {
  VOL_DOWN, VOL_UP, bandsFor, blockRadius, hasOhlc, hasVolume, hoverRow,
  planLines, toCandles, toVolumeBars, vol, type SeriesBar,
} from './zoneChart';
import type { Zone } from './zonePlan';

// Real HASI bars, 2026-08-16 payload.
const REAL: SeriesBar[] = [
  { date: '2026-08-12', open: 41.90, high: 42.40, low: 41.55, close: 42.30, volume: 812_004 },
  { date: '2026-08-13', open: 42.35, high: 42.60, low: 41.80, close: 41.95, volume: 640_112 },
  { date: '2026-08-14', open: 42.31, high: 43.05, low: 42.06, close: 42.12, volume: 531_156 },
];

const zone = (o: Partial<Zone>): Zone => ({
  kind: 'demand', lo: 39, hi: 40, mid: 39.5, touches: 2, volume: 1e6,
  bars_since_test: 4, strength: 1, ...o,
});

describe('toCandles', () => {
  it('maps real bars straight through', () => {
    const c = toCandles(REAL);
    expect(c).toHaveLength(3);
    expect(c[2]).toEqual({ time: '2026-08-14', open: 42.31, high: 43.05, low: 42.06, close: 42.12 });
  });

  it('degenerates a close-only bar to a doji rather than dropping it', () => {
    // A hole would shift every later bar and silently mis-place the bands
    // against the price — a flat candle is visibly odd, a shifted chart is not.
    const c = toCandles([{ date: '2026-08-14', close: 42.12 }]);
    expect(c[0]).toEqual({ time: '2026-08-14', open: 42.12, high: 42.12, low: 42.12, close: 42.12 });
  });

  it('clamps a high that sits below the body', () => {
    const c = toCandles([{ date: '2026-08-14', open: 40, high: 39, low: 38, close: 42 }]);
    expect(c[0].high).toBe(42);
    expect(c[0].low).toBe(38);
  });

  it('clamps a low that sits above the body', () => {
    const c = toCandles([{ date: '2026-08-14', open: 40, high: 43, low: 41.5, close: 41 }]);
    expect(c[0].low).toBe(40);
  });

  // --- negatives ---
  it('drops out-of-order and duplicate dates the library would reject', () => {
    const c = toCandles([
      { date: '2026-08-14', close: 1 },
      { date: '2026-08-14', close: 2 },   // duplicate
      { date: '2026-08-13', close: 3 },   // backwards
      { date: '2026-08-15', close: 4 },
    ]);
    expect(c.map((x) => x.time)).toEqual(['2026-08-14', '2026-08-15']);
  });

  it('drops bars with no usable close', () => {
    const c = toCandles([
      { date: '2026-08-12', close: NaN as unknown as number },
      { date: '2026-08-13', close: null as unknown as number },
      { date: '2026-08-14', close: 42 },
    ]);
    expect(c).toHaveLength(1);
  });

  it('survives junk input', () => {
    expect(toCandles(undefined)).toEqual([]);
    expect(toCandles(null)).toEqual([]);
    expect(toCandles([] as SeriesBar[])).toEqual([]);
    expect(toCandles([{ date: '', close: 1 }])).toEqual([]);
    expect(toCandles([null as unknown as SeriesBar])).toEqual([]);
  });
});

describe('toVolumeBars', () => {
  it('colours each bar by its own direction', () => {
    const v = toVolumeBars(REAL);
    expect(v).toHaveLength(3);
    expect(v[0].color).toBe(VOL_UP);      // 42.30 close vs 41.90 open
    expect(v[1].color).toBe(VOL_DOWN);    // 41.95 close vs 42.35 open
    expect(v[2].value).toBe(531_156);
  });

  it('treats an unchanged close as up, matching the candle body', () => {
    expect(toVolumeBars([{ date: '2026-08-14', open: 42, close: 42, volume: 10 }])[0].color)
      .toBe(VOL_UP);
  });

  // --- negatives ---
  it('OMITS a bar with no volume rather than drawing a zero column', () => {
    // A zero column reads as "nobody traded", which is a claim a missing field
    // does not support.
    const v = toVolumeBars([
      { date: '2026-08-13', close: 42, volume: null },
      { date: '2026-08-14', close: 42, volume: 0 },
      { date: '2026-08-15', close: 42, volume: 100 },
    ]);
    expect(v.map((x) => x.time)).toEqual(['2026-08-15']);
  });

  it('still rejects out-of-order dates', () => {
    const v = toVolumeBars([
      { date: '2026-08-15', close: 1, volume: 5 },
      { date: '2026-08-14', close: 1, volume: 5 },
    ]);
    expect(v).toHaveLength(1);
  });

  it('survives junk input', () => {
    expect(toVolumeBars(undefined)).toEqual([]);
    expect(toVolumeBars([{ date: 'x', close: NaN as unknown as number, volume: 5 }])).toEqual([]);
  });
});

describe('hasOhlc / hasVolume — what this payload can actually draw', () => {
  it('recognises a full payload', () => {
    expect(hasOhlc(REAL)).toBe(true);
    expect(hasVolume(REAL)).toBe(true);
  });

  it('recognises a pre-2026-08-16 cached payload as line-only', () => {
    const old = [{ date: '2026-08-14', close: 42.12 }];
    expect(hasOhlc(old)).toBe(false);
    expect(hasVolume(old)).toBe(false);
  });

  it('is false on empty and junk', () => {
    expect(hasOhlc([])).toBe(false);
    expect(hasOhlc(undefined)).toBe(false);
    expect(hasVolume(null)).toBe(false);
  });
});

describe('vol — a count, never a price', () => {
  it('compacts at each magnitude', () => {
    expect(vol(531_156)).toBe('531K');
    expect(vol(1_440_000)).toBe('1.44M');
    expect(vol(2_300_000_000)).toBe('2.30B');
    expect(vol(842)).toBe('842');
  });

  it('shows a dash rather than NaN', () => {
    expect(vol(null)).toBe('—');
    expect(vol(undefined)).toBe('—');
    expect(vol(NaN)).toBe('—');
    expect(vol(-5)).toBe('—');
  });
});

describe('hoverRow — the thing he asked for', () => {
  const bar = { time: '2026-08-14', open: 42.31, high: 43.05, low: 42.06, close: 42.12 };

  it('reads out the whole bar', () => {
    const r = hoverRow(bar, 531_156, 41.95)!;
    expect(r.date).toBe('2026-08-14');
    expect(r.open).toBe('$42.31');
    expect(r.high).toBe('$43.05');
    expect(r.low).toBe('$42.06');
    expect(r.close).toBe('$42.12');
    expect(r.volume).toBe('531K');
  });

  it('computes the change against the PREVIOUS CLOSE, not the open', () => {
    // 42.12 vs 41.95 = +0.41%. Against its own open it would be -0.45%, a
    // different statistic wearing the same label.
    expect(hoverRow(bar, null, 41.95)!.changePct).toBe('+0.41%');
  });

  it('signs a down day', () => {
    expect(hoverRow(bar, null, 43.00)!.changePct).toBe('-2.05%');
  });

  it('marks direction from the candle body', () => {
    expect(hoverRow(bar, null, null)!.up).toBe(false);      // 42.12 < 42.31 open
    expect(hoverRow({ ...bar, open: 41 }, null, null)!.up).toBe(true);
  });

  // --- negatives ---
  it('omits the change rather than inventing a baseline', () => {
    expect(hoverRow(bar, null, null)!.changePct).toBeNull();
    expect(hoverRow(bar, null, 0)!.changePct).toBeNull();
  });

  it('is null for no bar', () => {
    expect(hoverRow(null)).toBeNull();
    expect(hoverRow(undefined)).toBeNull();
    expect(hoverRow({ ...bar, close: NaN })).toBeNull();
  });

  it('drops cents on four-figure stocks but keeps them below', () => {
    expect(hoverRow({ time: 't', open: 1258.17, high: 1300, low: 1200, close: 1273.4 })!.close)
      .toBe('$1273');
  });
});

describe('planLines', () => {
  const ez = zone({ lo: 39.02, hi: 40.11 });
  const data = {
    entry_zone: ez,
    last_price: 42.12,
    plan: { entry_low: 39.02, entry_high: 40.11, entry_ref: 40.11, stop: 38.68,
            risk_pct: 3.6, target: 43.36, reward_pct: 8.1, rr: 2.2,
            risk_exceeds_max: false, max_stop_pct: 10 },
  };

  it('draws both edges of the buy band, the stop, the target and now', () => {
    const l = planLines(data);
    expect(l.map((x) => x.title)).toEqual([
      'BUY $40.11', 'BUY $39.02', 'STOP $38.68', 'TARGET $43.36', 'NOW $42.12',
    ]);
  });

  it('always keeps cents — these are numbers he types into a broker', () => {
    const l = planLines({ ...data, last_price: 1258.5, entry_zone: null,
                          plan: { ...data.plan, stop: 98.5, target: null } });
    expect(l.find((x) => x.title.startsWith('STOP'))!.title).toBe('STOP $98.50');
    expect(l.find((x) => x.title.startsWith('NOW'))!.title).toBe('NOW $1258.50');
  });

  it('dashes the exits and leaves the band edges solid', () => {
    const l = planLines(data);
    expect(l.find((x) => x.title.startsWith('BUY'))!.dashed).toBe(false);
    expect(l.find((x) => x.title.startsWith('STOP'))!.dashed).toBe(true);
  });

  // --- negatives ---
  it('omits a target the backend could not compute', () => {
    const l = planLines({ ...data, plan: { ...data.plan, target: null } });
    expect(l.some((x) => x.title.startsWith('TARGET'))).toBe(false);
  });

  it('draws NOW even with no plan at all', () => {
    const l = planLines({ entry_zone: null, plan: null, last_price: 42.12 });
    expect(l).toHaveLength(1);
    expect(l[0].title).toBe('NOW $42.12');
  });

  it('is empty for junk', () => {
    expect(planLines(null)).toEqual([]);
    expect(planLines({ entry_zone: null, plan: null, last_price: NaN })).toEqual([]);
  });
});

describe('bandsFor', () => {
  const ez = zone({ lo: 39.02, hi: 40.11 });

  it('marks the entry band by its own edges, not by a clipped coincidence', () => {
    const b = bandsFor({
      supply_zones: [zone({ kind: 'supply', lo: 43, hi: 44 })],
      demand_zones: [ez, zone({ lo: 31, hi: 32 })],
      entry_zone: ez,
    });
    expect(b).toHaveLength(3);
    expect(b.filter((x) => x.isEntry)).toHaveLength(1);
    expect(b.find((x) => x.isEntry)!.lo).toBe(39.02);
  });

  it('never marks a supply band as the entry', () => {
    const s = zone({ kind: 'supply', lo: 39.02, hi: 40.11 });
    const b = bandsFor({ supply_zones: [s], demand_zones: [], entry_zone: ez });
    expect(b[0].isEntry).toBe(false);
  });

  // --- negatives ---
  it('drops zero-height bands that would read as a price level', () => {
    const b = bandsFor({
      supply_zones: [zone({ kind: 'supply', lo: 40, hi: 40 })],
      demand_zones: [], entry_zone: null,
    });
    expect(b).toEqual([]);
  });

  it('drops inverted and non-finite bands', () => {
    const b = bandsFor({
      supply_zones: [zone({ kind: 'supply', lo: 44, hi: 43 })],
      demand_zones: [zone({ lo: NaN, hi: 40 })],
      entry_zone: null,
    });
    expect(b).toEqual([]);
  });

  it('marks nothing when there is no entry zone', () => {
    const b = bandsFor({ supply_zones: [], demand_zones: [zone({})], entry_zone: null });
    expect(b[0].isEntry).toBe(false);
  });

  it('survives junk', () => {
    expect(bandsFor(null)).toEqual([]);
    expect(bandsFor({ supply_zones: undefined as unknown as Zone[],
                      demand_zones: undefined as unknown as Zone[],
                      entry_zone: null })).toEqual([]);
  });
});

describe('blockRadius', () => {
  it('scales with the square root of notional', () => {
    expect(blockRadius(18e6, 18e6)).toBeCloseTo(5.8);
    expect(blockRadius(0, 18e6)).toBeCloseTo(2.2);
  });
  it('is zero rather than NaN for junk', () => {
    expect(blockRadius(1, 0)).toBe(0);
    expect(blockRadius(NaN, 10)).toBe(0);
  });
});
