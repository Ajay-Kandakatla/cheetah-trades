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
  DEMAND, NEUTRAL, VOL_DOWN, VOL_UP, bandsFor, blockRadius, gutterBars, hasOhlc, hasVolume, hoverRow, planGutterPx, planLines, toCandles, toVolumeBars, type SeriesBar, vol,
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

  it('draws ONE buy line carrying the whole band, the stop, the target and now', () => {
    // Ajay 2026-08-17: "There are two different buys in the NBIX stock one on
    // chart". Two lines each labelled `BUY $x` at different prices read as two
    // competing entries. One label, one range.
    const l = planLines(data);
    expect(l.map((x) => x.title)).toEqual([
      'BUY $39.02–$40.11', 'STOP $38.68', 'TARGET $43.36', 'NOW $42.12',
    ]);
  });

  it('anchors the buy line at the band TOP, away from the stop label', () => {
    // The floor sits ~1.5% above the stop; both axis labels would land on the
    // same pixels and neither would be readable.
    expect(planLines(data).find((x) => x.title.startsWith('BUY'))!.price).toBe(40.11);
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

/* ═══════════════════════════════════════════════════════════════════════════
 * THE BROKEN BAND — Ajay 2026-08-17, on NBIX:
 *   "There are two different buys in the NBIX stock one on chart, We fell
 *    below the demand zone but you still say buy in one place."
 * Spec: docs/supply_demand/broken_band_guard.md
 * ═══════════════════════════════════════════════════════════════════════════ */
describe('a band that BROKE never says BUY', () => {
  const ez = zone({ lo: 152.54, hi: 155.3 });
  const nbix = {
    entry_zone: ez,
    last_price: 152.72,
    plan: { entry_low: 152.54, entry_high: 155.3, entry_ref: 152.72, stop: 150.25,
            risk_pct: 1.6, target: 157.67, reward_pct: 3.2, rr: 2.0,
            risk_exceeds_max: false, max_stop_pct: 10 },
  };

  it('relabels the buy line BROKEN', () => {
    const l = planLines({ ...nbix, zone_broken: true });
    expect(l.map((x) => x.title)).toEqual([
      'BROKEN $152.54–$155.30', 'STOP $150.25', 'TARGET $157.67', 'NOW $152.72',
    ]);
    expect(l.some((x) => x.title.includes('BUY'))).toBe(false);
  });

  it('drains the buy colour out of the line so it does not read as green light', () => {
    const broken = planLines({ ...nbix, zone_broken: true })[0];
    const live = planLines(nbix)[0];
    expect(live.color).toBe(DEMAND);
    expect(broken.color).toBe(NEUTRAL);
    expect(broken.dashed).toBe(true);
  });

  it('stops highlighting it as the ENTRY band on the chart', () => {
    // isEntry is what gives a band the strong fill and the outline on both
    // edges — the visual claim "this is the plan".
    const b = bandsFor({ supply_zones: [], demand_zones: [ez], entry_zone: ez,
                         zone_broken: true });
    expect(b).toHaveLength(1);
    expect(b[0].isEntry).toBe(false);
  });

  it('still DRAWS the band — it is still a demand band, just a broken one', () => {
    const b = bandsFor({ supply_zones: [], demand_zones: [ez], entry_zone: ez,
                         zone_broken: true });
    expect(b[0]).toMatchObject({ lo: 152.54, hi: 155.3, kind: 'demand' });
  });

  // --- negatives: absence of the flag must not be read as a break ---
  it('an older payload with no zone_broken field draws the normal BUY line', () => {
    expect(planLines(nbix)[0].title).toBe('BUY $152.54–$155.30');
    expect(bandsFor({ supply_zones: [], demand_zones: [ez], entry_zone: ez })[0].isEntry)
      .toBe(true);
  });

  it('only a literal true breaks it — undefined and false do not', () => {
    for (const v of [undefined, false]) {
      expect(planLines({ ...nbix, zone_broken: v })[0].title).toBe('BUY $152.54–$155.30');
    }
  });
});

describe('a stop the market already ran', () => {
  const base = {
    entry_zone: zone({ lo: 152.54, hi: 155.3 }),
    last_price: 152.72,
    plan: { entry_low: 152.54, entry_high: 155.3, entry_ref: 152.72, stop: 150.25,
            risk_pct: 1.6, target: null, reward_pct: null, rr: null,
            risk_exceeds_max: false, max_stop_pct: 10 },
  };

  it('says STOP HIT — labelling it STOP implies it is still ahead of price', () => {
    const l = planLines({ ...base,
      plan: { ...base.plan, stop_recently_hit: true, bars_since_stop_hit: 0 } });
    expect(l.find((x) => x.title.includes('150.25'))!.title).toBe('STOP HIT $150.25');
  });

  it('leaves a clean stop alone', () => {
    const l = planLines({ ...base, plan: { ...base.plan, stop_recently_hit: false } });
    expect(l.find((x) => x.title.includes('150.25'))!.title).toBe('STOP $150.25');
  });

  it('treats "not checked" (null) as not hit — it is not evidence of a hit', () => {
    const l = planLines({ ...base, plan: { ...base.plan, stop_recently_hit: null } });
    expect(l.find((x) => x.title.includes('150.25'))!.title).toBe('STOP $150.25');
  });
});

/* ── the plan labels moved off the candles (Ajay 2026-08-17) ─────────────── */

describe('every plan level is identifiable on its own', () => {
  const data = {
    entry_zone: zone({ lo: 64.41, hi: 66.08 }),
    last_price: 64.40,
    plan: { entry_low: 64.41, entry_high: 66.08, entry_ref: 66.08, stop: 63.44,
            risk_pct: 4.0, target: 70.88, reward_pct: 7.3, rr: 1.8,
            risk_exceeds_max: false, max_stop_pct: 10, stop_recently_hit: true,
            bars_since_stop_hit: 0, lowest_low_pct_below_stop: 1.2,
            stop_hit_lookback_bars: 10 },
  } as never;

  it('gives TARGET a colour of its own, not the BUY band green', () => {
    // The axis chip is colour + number and nothing else, so two levels sharing
    // a colour are indistinguishable there — and the chip is what survives when
    // a plate is displaced or dropped.
    const l = planLines(data);
    const buy = l.find((x) => x.kind === 'buy')!;
    const target = l.find((x) => x.kind === 'target')!;
    expect(target.color).not.toBe(buy.color);
    expect(new Set(l.map((x) => x.color)).size).toBe(l.length);
  });

  it('tags each line with WHAT it is rather than leaving the title to be parsed', () => {
    // `title.startsWith('STOP')` is wrong on arrival: the titles already read
    // "STOP HIT" and "BROKEN".
    expect(planLines(data).map((x) => x.kind).sort())
      .toEqual(['buy', 'now', 'stop', 'target']);
  });

  it('ranks the stop first to survive and NOW last', () => {
    // When a short pane cannot hold four plates, the stop is the number that
    // caps the loss; NOW is already on the axis and on the newest candle.
    const byKind = Object.fromEntries(planLines(data).map((x) => [x.kind, x.priority]));
    expect(byKind.stop).toBeLessThan(byKind.buy);
    expect(byKind.now).toBeGreaterThan(byKind.target);
  });

  it('always states the price inside the label text', () => {
    // A displaced plate must not need its y read to know what it means.
    for (const l of planLines(data)) expect(l.title).toMatch(/\$\d/);
  });
});

describe('planGutterPx', () => {
  const spec = (title: string) =>
    ({ price: 1, color: '#fff', title, dashed: false, bold: false,
       kind: 'buy', priority: 1 }) as never;

  it('reserves more room for a longer label', () => {
    const narrow = planGutterPx([spec('NOW $9.10')], 900);
    const wide = planGutterPx([spec('BUY $1,485.00-$1,514.00')], 900);
    expect(wide).toBeGreaterThan(narrow);
  });

  it('sizes to the WIDEST label, not the last one', () => {
    expect(planGutterPx([spec('BUY $1,485.00-$1,514.00'), spec('NOW $9.10')], 900))
      .toBe(planGutterPx([spec('BUY $1,485.00-$1,514.00')], 900));
  });

  it('never eats more than a third of the pane', () => {
    // A plate overhanging a few candles beats a chart with no candles left.
    expect(planGutterPx([spec('BUY $1,485.00-$1,514.00')], 240))
      .toBeLessThanOrEqual(80);
  });

  // --- negatives ---
  it('reserves nothing when there is nothing to label', () => {
    expect(planGutterPx([], 900)).toBe(0);
    expect(planGutterPx(null, 900)).toBe(0);
    expect(planGutterPx(undefined, 900)).toBe(0);
  });

  it('reserves nothing before the pane has been measured', () => {
    expect(planGutterPx([spec('NOW $9.10')], 0)).toBe(0);
    expect(planGutterPx([spec('NOW $9.10')], -5)).toBe(0);
  });
});

describe('gutterBars', () => {
  it('converts a pixel margin into the bar slots the time scale wants', () => {
    // b / (n + b) = g / w. 100 bars, 600px pane, 60px gutter -> ~11 bars.
    const b = gutterBars(100, 600, 60);
    expect(b).toBeGreaterThan(0);
    expect(Math.abs(60 / 600 - b / (100 + b))).toBeLessThan(0.02);
  });

  it('asks for more bars as the margin grows', () => {
    expect(gutterBars(100, 600, 120)).toBeGreaterThan(gutterBars(100, 600, 60));
  });

  // --- negatives ---
  it('asks for nothing rather than infinity when the gutter swallows the pane', () => {
    // w - g <= 0 would divide by zero or go negative and blank the chart.
    expect(gutterBars(100, 60, 60)).toBe(0);
    expect(gutterBars(100, 40, 60)).toBe(0);
  });

  it('asks for nothing with no bars or no gutter', () => {
    expect(gutterBars(0, 600, 60)).toBe(0);
    expect(gutterBars(100, 600, 0)).toBe(0);
    expect(gutterBars(100, 600, -10)).toBe(0);
  });
});
